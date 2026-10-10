"""Запуск решения на Python под аудит-хуком (PEP 578).

``python -I -S -B pyboot.py solution.py``. Хук ставится до кода решения и
снимается только вместе с процессом. Он дублирует запреты ядра понятными
сообщениями (вердикт RE с причиной) и закрывает то, что ядро не видит:
импорт ctypes, _posixsubprocess, сокетов и многопроцессности, чтение файлов
вне стандартной библиотеки. Модуль самодостаточен.
"""

import sys

CE_EXIT = 86
VIOLATION_EXIT = 87


def _boot() -> None:
    import os

    path = sys.argv[1]
    with open(path, encoding='utf-8') as fh:
        source = fh.read()
    try:
        code = compile(source, 'solution.py', 'exec')
    except (SyntaxError, ValueError) as exc:
        line = getattr(exc, 'lineno', None)
        sys.stderr.write(
            f'{type(exc).__name__}: {getattr(exc, "msg", exc)}' + (f' (строка {line})' if line else '') + '\n'
        )
        sys.stderr.flush()
        os._exit(CE_EXIT)

    stdlib = os.path.dirname(os.__file__)
    allowed_read = (
        stdlib + os.sep,
        os.path.realpath(stdlib) + os.sep,
        os.path.realpath(__file__),
        '/dev/null',
        '/dev/urandom',
    )
    blocked_events = (
        'socket.',
        'subprocess.',
        'os.system',
        'os.exec',
        'os.posix_spawn',
        'os.spawn',
        'os.fork',
        'os.forkpty',
        'os.kill',
        'os.killpg',
        'signal.pthread_kill',
        'ctypes.',
        'os.remove',
        'os.rename',
        'os.rmdir',
        'os.mkdir',
        'os.chmod',
        'os.chown',
        'os.symlink',
        'os.link',
        'os.truncate',
        'os.chdir',
        'os.putenv',
        'os.unsetenv',
        'os.listxattr',
        'shutil.',
        'resource.setrlimit',
        'resource.prlimit',
        'pty.',
        'sys.remote_exec',
        'webbrowser.',
    )
    blocked_modules = frozenset(
        {
            '_ctypes',
            'ctypes',
            '_posixsubprocess',
            'subprocess',
            '_socket',
            'socket',
            '_ssl',
            'ssl',
            'multiprocessing',
            '_multiprocessing',
            'pty',
            'fcntl',
            'mmap',
            'gc',
            '_xxsubinterpreters',
            '_interpreters',
            'threading',
            '_thread',
        }
    )
    write_flags = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
    realpath = os.path.realpath
    exit_now = os._exit
    write_err = sys.stderr.write
    flush_err = sys.stderr.flush

    def deny(what: str) -> None:
        write_err(f'Запрещённая операция в песочнице: {what}\n')
        flush_err()
        exit_now(VIOLATION_EXIT)

    def hook(event: str, args: tuple) -> None:
        if event == 'open':
            target, mode, flags = args
            if isinstance(target, int):
                if target in (0, 1, 2):
                    return
                deny('open(fd)')
            if (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (
                isinstance(flags, int) and flags & write_flags
            ):
                deny('запись файла')
            name = target.decode() if isinstance(target, bytes) else str(target)
            full = realpath(name)
            if full == realpath(path) or full in allowed_read or full.startswith(allowed_read):
                return
            deny(f'чтение файла {name}')
        elif event in ('os.listdir', 'os.scandir'):
            target = args[0]
            name = '.' if target is None else (target.decode() if isinstance(target, bytes) else str(target))
            full = realpath(name) + os.sep
            if not (full.startswith(allowed_read) or full == realpath('.') + os.sep):
                deny(f'просмотр каталога {name}')
        elif event == 'import':
            if args[0] in blocked_modules:
                deny(f'import {args[0]}')
        elif event.startswith(blocked_events):
            deny(event)

    sys.addaudithook(hook)
    sys.argv = ['solution.py']
    try:
        exec(code, {'__name__': '__main__', '__builtins__': __builtins__})
    except SystemExit:
        raise
    except BaseException as exc:  # traceback без кадров загрузчика
        import traceback

        traceback.print_exception(type(exc), exc, exc.__traceback__.tb_next if exc.__traceback__ else None)
        sys.stderr.flush()
        exit_now(1)


_boot()
