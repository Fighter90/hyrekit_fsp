"""Проверка решений: запуск в песочнице, вердикты по тестам.

Каждый тест — отдельный процесс ``sandbox.py`` → exec интерпретатора с
лимитами ОС, Landlock и seccomp; Python дополнительно под аудит-хуком
(``pyboot.py``). Вердикты: OK, WA, TLE, MLE, RE, CE.

Числа (лимиты, параллелизм) — константы этого модуля.
"""

from __future__ import annotations

import asyncio
import contextlib
import functools
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SANDBOX = HERE / 'sandbox.py'
PYBOOT = HERE / 'pyboot.py'

TIME_LIMIT_S = 2.0  # процессорное время на тест
WALL_FACTOR = 3.0  # настенное время = TIME_LIMIT_S · WALL_FACTOR + 1 с (ожидание ввода, ядро под нагрузкой)
MEMORY_MB = 256
OUTPUT_LIMIT_KB = 1024
CODE_LIMIT_KB = 64
MAX_PARALLEL = 2  # одновременных процессов решения на процесс приложения
STDERR_TAIL = 2000

PY_CE_EXIT = 86
PY_VIOLATION_EXIT = 87
SANDBOX_UNAVAILABLE_EXIT = 97

VERDICT_TITLES = {
    'OK': 'Верно',
    'WA': 'Неверный ответ',
    'TLE': 'Превышено время',
    'MLE': 'Превышена память',
    'RE': 'Ошибка выполнения',
    'CE': 'Ошибка компиляции',
}
LANGUAGE_TITLES = {'python': 'Python 3', 'javascript': 'JavaScript (Node.js)'}

_slots = threading.BoundedSemaphore(MAX_PARALLEL)


@dataclass
class TestCase:
    __test__ = False  # не тестовый класс pytest

    input: str
    expected: str
    sample: bool = False


@dataclass
class TestResult:
    __test__ = False  # не тестовый класс pytest

    verdict: str
    time_ms: int
    memory_kb: int
    sample: bool = False
    message: str | None = None
    output: str | None = None


@dataclass
class JudgeResult:
    verdict: str
    passed: int
    total: int
    time_ms: int
    memory_kb: int
    tests: list[TestResult] = field(default_factory=list)
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _system_lib_dirs() -> list[str]:
    return [
        '/lib',
        '/lib64',
        '/usr/lib',
        '/usr/lib64',
        '/usr/local/lib',
        '/etc/ld.so.cache',
        '/etc/ld.so.conf',
        '/etc/ld.so.conf.d',
    ]


def _loader_dirs() -> list[str]:
    """Каталоги динамического загрузчика: ядро открывает его при exec как исполняемый."""
    return [
        '/lib64',
        '/lib/x86_64-linux-gnu',
        '/usr/lib/x86_64-linux-gnu',
        '/lib/ld-linux-aarch64.so.1',
        '/lib/aarch64-linux-gnu',
    ]


def _node_binary() -> str | None:
    return shutil.which('node')


@functools.cache
def capabilities() -> dict[str, Any]:
    """Какие слои песочницы работают на этом ядре и какие языки включены."""
    probe = {'read': _system_lib_dirs(), 'exec': [os.path.realpath(sys.executable)]}
    try:
        out = subprocess.run(
            [sys.executable, '-I', '-S', '-B', str(SANDBOX), '--probe', json.dumps(probe)],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        layers = json.loads(out.stdout or '{}')
    except Exception:
        layers = {}
    landlock = int(layers.get('landlock') or 0)
    seccomp = bool(layers.get('seccomp'))
    languages = ['python']
    # JavaScript без аудит-хука: включаем только при полной изоляции ядром.
    if landlock and seccomp and _node_binary():
        languages.append('javascript')
    return {'landlock': landlock, 'seccomp': seccomp, 'languages': languages}


def _command(language: str, workdir: str) -> tuple[list[str], dict[str, Any]]:
    """argv интерпретатора и лимиты под язык."""
    if language == 'python':
        exe = os.path.realpath(sys.executable)
        stdlib = os.path.dirname(os.__file__)
        argv = [exe, '-I', '-S', '-B', str(PYBOOT), 'solution.py']
        return argv, {
            'read': [
                *_system_lib_dirs(),
                stdlib,
                os.path.realpath(stdlib),
                str(PYBOOT),
                workdir,
                '/dev/null',
                '/dev/urandom',
            ],
            'exec': [exe, *_loader_dirs()],
            'address_space_mb': MEMORY_MB,
        }
    if language == 'javascript':
        node = os.path.realpath(_node_binary() or 'node')
        argv = [node, f'--max-old-space-size={MEMORY_MB - 32}', '--stack-size=4096', 'solution.js']
        return argv, {
            'read': [*_system_lib_dirs(), workdir, '/dev/null', '/dev/urandom', '/proc/self', '/sys/fs/cgroup'],
            'exec': [node, *_loader_dirs()],
            'data_mb': MEMORY_MB * 2,
            'require_kernel': True,
            'env': {'LANG': 'C.UTF-8', 'OPENSSL_CONF': '/dev/null'},
        }
    raise ValueError(f'Язык не поддерживается: {language}')


def _kill(pid: int) -> None:
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(pid, signal.SIGKILL)


def _run_process(argv: list[str], stdin: str, wall: float) -> dict[str, Any]:
    """Запуск с перехватом rusage: время процессора и пиковая память."""
    limit = OUTPUT_LIMIT_KB * 1024
    proc = subprocess.Popen(
        argv,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
        close_fds=True,
        env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'},
    )
    out = bytearray()
    err = bytearray()
    state = {'overflow': False, 'timeout': False}

    def feed() -> None:
        try:
            proc.stdin.write(stdin.encode())  # type: ignore[union-attr]
        except (BrokenPipeError, OSError):
            pass
        finally:
            with contextlib.suppress(OSError):
                proc.stdin.close()  # type: ignore[union-attr]

    def drain(stream: Any, buf: bytearray, cap: int, flag: str | None) -> None:
        seen = 0
        while chunk := stream.read(8192):
            seen += len(chunk)
            if len(buf) < cap:
                buf.extend(chunk[: cap - len(buf)])
            if flag and seen > cap and not state[flag]:
                state[flag] = True
                _kill(proc.pid)

    threads = [
        threading.Thread(target=feed, daemon=True),
        threading.Thread(target=drain, args=(proc.stdout, out, limit, 'overflow'), daemon=True),
        threading.Thread(target=drain, args=(proc.stderr, err, 64 * 1024, None), daemon=True),
    ]
    for t in threads:
        t.start()

    def on_timeout() -> None:
        state['timeout'] = True
        _kill(proc.pid)

    timer = threading.Timer(wall, on_timeout)
    timer.start()
    started = time.monotonic()
    try:
        _, status, usage = os.wait4(proc.pid, 0)
    finally:
        timer.cancel()
    elapsed = time.monotonic() - started
    proc.returncode = os.waitstatus_to_exitcode(status)
    _kill(proc.pid)
    for t in threads:
        t.join(timeout=2)
    return {
        'code': proc.returncode,
        'stdout': bytes(out[:limit]).decode('utf-8', 'replace'),
        'stderr': bytes(err).decode('utf-8', 'replace'),
        'cpu': usage.ru_utime + usage.ru_stime,
        'wall': elapsed,
        'maxrss_kb': int(usage.ru_maxrss),
        'overflow': state['overflow'],
        'timeout': state['timeout'],
    }


def normalize_output(text: str) -> list[str]:
    """Сравнение по токенам строк: лишние пробелы и пустые строки в конце не важны."""
    lines = [' '.join(line.split()) for line in text.strip().splitlines()]
    return list(lines)


def _classify(raw: dict[str, Any], language: str, expected: str) -> tuple[str, str | None]:
    code, stderr = raw['code'], raw['stderr']
    # Python пишет причину в конце traceback, Node — в начале
    tail = (stderr[-STDERR_TAIL:] if language == 'python' else stderr[:STDERR_TAIL]).strip() or None
    if raw['overflow']:
        return 'RE', f'Вывод больше {OUTPUT_LIMIT_KB} КБ'
    if code == SANDBOX_UNAVAILABLE_EXIT:
        return 'RE', 'Песочница недоступна на этом сервере'
    if language == 'python' and code == PY_CE_EXIT:
        return 'CE', tail
    if language == 'python' and code == PY_VIOLATION_EXIT:
        return 'RE', tail
    if raw['timeout'] or raw['cpu'] > TIME_LIMIT_S or code in (-signal.SIGXCPU, 128 + signal.SIGXCPU):
        return 'TLE', None
    mem_hit = raw['maxrss_kb'] > MEMORY_MB * 1024
    if mem_hit or 'MemoryError' in stderr or 'heap out of memory' in stderr or 'Allocation failed' in stderr:
        return 'MLE', None
    if language == 'javascript' and code != 0 and 'SyntaxError' in stderr and 'solution.js' in stderr[:400]:
        return 'CE', tail
    if code == -signal.SIGSEGV:
        return 'RE', 'Аварийное завершение (SIGSEGV): чаще всего слишком глубокая рекурсия'
    if code < 0:
        return 'RE', tail or f'Процесс завершён сигналом {signal.Signals(-code).name}'
    if code != 0:
        return 'RE', tail or f'Код завершения {code}'
    if normalize_output(raw['stdout']) != normalize_output(expected):
        return 'WA', None
    return 'OK', None


def judge_sync(
    language: str, code: str, tests: list[TestCase], *, stop_on_fail: bool = False, show_output: bool = False
) -> JudgeResult:
    """Прогон решения на тестах (блокирующий; вызывать из потока)."""
    if language not in capabilities()['languages']:
        raise ValueError(f'Язык недоступен: {language}')
    if len(code.encode()) > CODE_LIMIT_KB * 1024:
        raise ValueError(f'Код больше {CODE_LIMIT_KB} КБ')
    results: list[TestResult] = []
    with tempfile.TemporaryDirectory(prefix='arena-') as workdir:
        os.chmod(workdir, 0o755)
        name = 'solution.py' if language == 'python' else 'solution.js'
        Path(workdir, name).write_text(code, encoding='utf-8')
        argv, limits = _command(language, workdir)
        cfg = {
            'workdir': workdir,
            'argv': argv,
            'env': {'LANG': 'C.UTF-8', 'PYTHONIOENCODING': 'utf-8'},
            'cpu_seconds': int(TIME_LIMIT_S) + 1,
            **limits,
        }
        wrapper = [sys.executable, '-I', '-S', '-B', str(SANDBOX), json.dumps(cfg)]
        wall = TIME_LIMIT_S * WALL_FACTOR + 1
        for case in tests:
            with _slots:
                raw = _run_process(wrapper, case.input, wall)
            verdict, message = _classify(raw, language, case.expected)
            results.append(
                TestResult(
                    verdict=verdict,
                    time_ms=round(min(raw['cpu'], TIME_LIMIT_S * WALL_FACTOR) * 1000),
                    memory_kb=raw['maxrss_kb'],
                    sample=case.sample,
                    message=message,
                    output=raw['stdout'][:2000] if show_output else None,
                )
            )
            if verdict == 'CE' or (stop_on_fail and verdict != 'OK'):
                break
    passed = sum(r.verdict == 'OK' for r in results)
    first_bad = next((r for r in results if r.verdict != 'OK'), None)
    total = len(tests)
    if first_bad is None and len(results) == total:
        verdict, message = 'OK', None
    else:
        verdict = first_bad.verdict if first_bad else 'WA'
        message = first_bad.message if first_bad else None
    return JudgeResult(
        verdict=verdict,
        passed=passed,
        total=total,
        time_ms=max((r.time_ms for r in results), default=0),
        memory_kb=max((r.memory_kb for r in results), default=0),
        tests=results,
        message=message,
    )


async def judge(language: str, code: str, tests: list[TestCase], **kw: Any) -> JudgeResult:
    return await asyncio.to_thread(judge_sync, language, code, tests, **kw)
