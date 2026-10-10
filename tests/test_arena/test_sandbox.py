"""Песочница Arena (FSP-37): лимиты, запреты и вердикты."""

from __future__ import annotations

import pytest

from app.arena.judge import TestCase, capabilities, judge_sync

SUM = [TestCase('3 4\n', '7\n')]
OK_PY = 'a, b = map(int, input().split())\nprint(a + b)\n'


def run(code: str, language: str = 'python') -> tuple[str, str]:
    r = judge_sync(language, code, SUM)
    return r.verdict, r.message or ''


def test_python_verdicts() -> None:
    assert run(OK_PY)[0] == 'OK'
    assert run('print(1)')[0] == 'WA'
    assert run('print(')[0] == 'CE'
    assert run('1/0')[0] == 'RE'
    assert run('while True: pass')[0] == 'TLE'
    assert run('x = bytearray(600 * 1024 * 1024)')[0] == 'MLE'


@pytest.mark.parametrize(
    ('code', 'reason'),
    [
        ('import socket\nsocket.create_connection(("1.1.1.1", 80))', 'import socket'),
        ('__import__("_socket")', '_socket'),
        ('import os\nos.fork()', 'os.fork'),
        ('import os\nos.system("id")', 'os.system'),
        ('import subprocess', 'subprocess'),
        ('print(open("/etc/passwd").read())', '/etc/passwd'),
        ('print(open("/proc/1/environ").read())', '/proc/1/environ'),
        ('open("/tmp/arena-pwn", "w").write("x")', 'запись'),
        ('import ctypes', 'ctypes'),
        ('import os\nos.kill(1, 9)', 'os.kill'),
    ],
)
def test_python_attacks_are_blocked(code: str, reason: str) -> None:
    verdict, message = run(code)
    assert verdict == 'RE'
    assert reason in message


def test_kernel_layers_block_without_audit_hook() -> None:
    """Ядро режет сеть, fork и чтение файлов даже в обход аудит-хука."""
    import json
    import os
    import subprocess
    import sys

    from app.arena import judge

    caps = capabilities()
    if not (caps['landlock'] and caps['seccomp']):
        pytest.skip('ядро без Landlock или seccomp')
    exe = os.path.realpath(sys.executable)
    stdlib = os.path.dirname(os.__file__)
    for code in ('import socket; socket.socket()', 'import os; os.fork()', 'open("/etc/hostname").read()'):
        cfg = {
            'workdir': '/tmp',
            'argv': [exe, '-I', '-S', '-c', code],
            'cpu_seconds': 3,
            'read': [*judge._system_lib_dirs(), stdlib, os.path.realpath(stdlib)],
            'exec': [exe, *judge._loader_dirs()],
            'env': {},
        }
        r = subprocess.run(
            [sys.executable, '-I', '-S', '-B', str(judge.SANDBOX), json.dumps(cfg)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert r.returncode != 0
        assert 'PermissionError' in r.stderr


def test_output_limit() -> None:
    verdict, message = run('print("x" * 3_000_000)')
    assert verdict == 'RE'
    assert 'Вывод больше' in message


def test_stdin_ways_and_stdlib_imports() -> None:
    assert run('import sys\nd = sys.stdin.read().split()\nprint(int(d[0]) + int(d[1]))')[0] == 'OK'
    assert run('a, b = map(int, open(0).read().split())\nprint(a + b)')[0] == 'OK'
    assert run('import heapq, collections, itertools, bisect, math, functools, re\n' + OK_PY)[0] == 'OK'


def test_javascript_when_kernel_isolation_available() -> None:
    if 'javascript' not in capabilities()['languages']:
        pytest.skip('JavaScript выключен: нет node или изоляции ядром')
    js = "const [a,b]=require('fs').readFileSync(0,'utf8').trim().split(/\\s+/).map(Number);console.log(a+b)"
    assert run(js, 'javascript')[0] == 'OK'
    assert run('while(true){}', 'javascript')[0] == 'TLE'
    assert run("require('fs').readFileSync('/etc/passwd','utf8')", 'javascript')[0] == 'RE'
    assert run("require('child_process').execSync('id')", 'javascript')[0] == 'RE'
