"""Обёртка запуска решения: лимиты ОС, Landlock и seccomp, затем exec интерпретатора.

Запускается отдельным процессом: ``python -I -S -B sandbox.py <config-json>``.
Модуль самодостаточен (только стандартная библиотека), потому что в
изолированном режиме пакет приложения не импортируется.

Слои защиты, которые переживают exec и действуют на код решения:

* rlimit — процессорное время, память, размер файлов, открытые файлы, без core;
* Landlock — чтение только из каталогов интерпретатора, системных библиотек
  и рабочей папки решения; запись, удаление и создание файлов запрещены;
  на ядрах с Landlock ABI 4+ запрещены и TCP bind/connect;
* seccomp — запрещены сокеты, fork/vfork и clone нового процесса (потоки
  разрешены), ptrace, сигналы, смена пространств имён, монтирование,
  удаление и переименование файлов, открытие файла на запись.

Без Landlock или seccomp (другое ядро, другая архитектура) обёртка всё равно
применяет лимиты и сообщает, какие слои включились, через ``--probe``.
"""

from __future__ import annotations

import ctypes
import json
import os
import resource
import struct
import sys

# ── Landlock ────────────────────────────────────────────────────────────────
SYS_LANDLOCK_CREATE_RULESET = 444
SYS_LANDLOCK_ADD_RULE = 445
SYS_LANDLOCK_RESTRICT_SELF = 446
LANDLOCK_CREATE_RULESET_VERSION = 1
LANDLOCK_RULE_PATH_BENEATH = 1

FS_EXECUTE = 1 << 0
FS_WRITE_FILE = 1 << 1
FS_READ_FILE = 1 << 2
FS_READ_DIR = 1 << 3
FS_ALL_V1 = (1 << 13) - 1
FS_REFER = 1 << 13
FS_TRUNCATE = 1 << 14
FS_IOCTL_DEV = 1 << 15
NET_BIND_TCP = 1 << 0
NET_CONNECT_TCP = 1 << 1

O_PATH = 0o10000000
O_CLOEXEC = 0o2000000

# ── seccomp (x86_64) ────────────────────────────────────────────────────────
PR_SET_NO_NEW_PRIVS = 38
PR_SET_SECCOMP = 22
SECCOMP_MODE_FILTER = 2
AUDIT_ARCH_X86_64 = 0xC000003E
RET_ALLOW = 0x7FFF0000
RET_KILL = 0x80000000
RET_ERRNO = 0x00050000
EPERM, EACCES, ENOSYS = 1, 13, 38
CLONE_THREAD = 0x00010000
OPEN_WRITE_FLAGS = 0o1 | 0o2 | 0o100 | 0o1000  # O_WRONLY | O_RDWR | O_CREAT | O_TRUNC

# Номера системных вызовов x86_64, которые решению не нужны.
DENY_X86_64 = {
    41: 'socket',
    42: 'connect',
    43: 'accept',
    49: 'bind',
    50: 'listen',
    53: 'socketpair',
    288: 'accept4',
    57: 'fork',
    58: 'vfork',
    322: 'execveat',
    101: 'ptrace',
    62: 'kill',
    200: 'tkill',
    234: 'tgkill',
    310: 'process_vm_readv',
    311: 'process_vm_writev',
    272: 'unshare',
    308: 'setns',
    165: 'mount',
    166: 'umount2',
    155: 'pivot_root',
    161: 'chroot',
    248: 'add_key',
    249: 'request_key',
    250: 'keyctl',
    321: 'bpf',
    298: 'perf_event_open',
    323: 'userfaultfd',
    425: 'io_uring_setup',
    426: 'io_uring_enter',
    427: 'io_uring_register',
    135: 'personality',
    133: 'mknod',
    259: 'mknodat',
    82: 'rename',
    264: 'renameat',
    316: 'renameat2',
    83: 'mkdir',
    258: 'mkdirat',
    84: 'rmdir',
    85: 'creat',
    86: 'link',
    265: 'linkat',
    87: 'unlink',
    263: 'unlinkat',
    88: 'symlink',
    266: 'symlinkat',
    90: 'chmod',
    91: 'fchmod',
    268: 'fchmodat',
    92: 'chown',
    93: 'fchown',
    94: 'lchown',
    260: 'fchownat',
    76: 'truncate',
    77: 'ftruncate',
    169: 'reboot',
    246: 'kexec_load',
    175: 'init_module',
    313: 'finit_module',
}
# Новые вызовы без разбора аргументов: ENOSYS, чтобы libc перешла на старый вариант.
ENOSYS_X86_64 = {435: 'clone3', 437: 'openat2'}
NR_OPEN, NR_OPENAT, NR_CLONE = 2, 257, 56


def _libc() -> ctypes.CDLL:
    return ctypes.CDLL(None, use_errno=True)


def landlock_abi() -> int:
    try:
        abi = _libc().syscall(SYS_LANDLOCK_CREATE_RULESET, None, 0, LANDLOCK_CREATE_RULESET_VERSION)
    except Exception:
        return 0
    return max(0, int(abi))


def apply_landlock(read_paths: list[str], exec_paths: list[str]) -> int:
    """Ограничивает файловую систему (и TCP на ABI 4+). Возвращает ABI или 0."""
    abi = landlock_abi()
    if abi <= 0:
        return 0
    libc = _libc()
    handled = FS_ALL_V1
    if abi >= 2:
        handled |= FS_REFER
    if abi >= 3:
        handled |= FS_TRUNCATE
    if abi >= 5:
        handled |= FS_IOCTL_DEV
    attr = struct.pack('=QQ', handled, NET_BIND_TCP | NET_CONNECT_TCP) if abi >= 4 else struct.pack('=Q', handled)
    buf = ctypes.create_string_buffer(attr, len(attr))
    ruleset = libc.syscall(SYS_LANDLOCK_CREATE_RULESET, buf, len(attr), 0)
    if ruleset < 0:
        return 0
    try:
        for path, access in [
            *((p, FS_READ_FILE | FS_READ_DIR) for p in read_paths),
            *((p, FS_EXECUTE | FS_READ_FILE | FS_READ_DIR) for p in exec_paths),
        ]:
            if not os.path.exists(path):
                continue
            fd = os.open(path, O_PATH | O_CLOEXEC)
            try:
                if not os.path.isdir(path):
                    access &= ~FS_READ_DIR
                rule = ctypes.create_string_buffer(struct.pack('=Qi', access, fd), 12)
                if libc.syscall(SYS_LANDLOCK_ADD_RULE, ruleset, LANDLOCK_RULE_PATH_BENEATH, rule, 0) < 0:
                    raise OSError(ctypes.get_errno(), f'landlock_add_rule {path}')
            finally:
                os.close(fd)
        if libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
            return 0
        if libc.syscall(SYS_LANDLOCK_RESTRICT_SELF, ruleset, 0) < 0:
            return 0
    finally:
        os.close(ruleset)
    return abi


def _bpf(code: int, jt: int, jf: int, k: int) -> bytes:
    return struct.pack('=HBBI', code, jt, jf, k)


LD_W_ABS, JEQ, JGE, JSET, RET = 0x20, 0x15, 0x35, 0x45, 0x06


def seccomp_program() -> bytes:
    prog = [
        _bpf(LD_W_ABS, 0, 0, 4),  # arch
        _bpf(JEQ, 1, 0, AUDIT_ARCH_X86_64),
        _bpf(RET, 0, 0, RET_KILL),
        _bpf(LD_W_ABS, 0, 0, 0),  # nr
        _bpf(JGE, 0, 1, 0x40000000),  # x32 ABI
        _bpf(RET, 0, 0, RET_ERRNO | EPERM),
    ]
    for nr in DENY_X86_64:
        prog += [_bpf(JEQ, 0, 1, nr), _bpf(RET, 0, 0, RET_ERRNO | EPERM)]
    for nr in ENOSYS_X86_64:
        prog += [_bpf(JEQ, 0, 1, nr), _bpf(RET, 0, 0, RET_ERRNO | ENOSYS)]
    # open(path, flags) и openat(dirfd, path, flags): запись и создание файлов запрещены
    for nr, arg in ((NR_OPEN, 1), (NR_OPENAT, 2)):
        prog += [
            _bpf(LD_W_ABS, 0, 0, 0),
            _bpf(JEQ, 0, 3, nr),
            _bpf(LD_W_ABS, 0, 0, 16 + 8 * arg),
            _bpf(JSET, 0, 1, OPEN_WRITE_FLAGS),
            _bpf(RET, 0, 0, RET_ERRNO | EACCES),
        ]
    # clone: только потоки (CLONE_THREAD); новый процесс запрещён. Блок последний.
    prog += [
        _bpf(LD_W_ABS, 0, 0, 0),
        _bpf(JEQ, 0, 3, NR_CLONE),
        _bpf(LD_W_ABS, 0, 0, 16),
        _bpf(JSET, 1, 0, CLONE_THREAD),
        _bpf(RET, 0, 0, RET_ERRNO | EPERM),
        _bpf(RET, 0, 0, RET_ALLOW),
    ]
    return b''.join(prog)


def apply_seccomp() -> bool:
    if os.uname().machine != 'x86_64':
        return False
    libc = _libc()
    prog = seccomp_program()
    n = len(prog) // 8
    filt = ctypes.create_string_buffer(prog, len(prog))

    class SockFprog(ctypes.Structure):
        _fields_ = [('len', ctypes.c_ushort), ('filter', ctypes.c_void_p)]

    fprog = SockFprog(n, ctypes.cast(filt, ctypes.c_void_p))
    if libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
        return False
    return libc.prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, ctypes.byref(fprog), 0, 0) == 0


def apply_rlimits(cfg: dict) -> None:
    cpu = int(cfg['cpu_seconds'])
    resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu + 1))
    if cfg.get('address_space_mb'):
        size = int(cfg['address_space_mb']) * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (size, size))
    if cfg.get('data_mb'):
        size = int(cfg['data_mb']) * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_DATA, (size, size))
    fsize = int(cfg.get('file_size_kb', 1024)) * 1024
    resource.setrlimit(resource.RLIMIT_FSIZE, (fsize, fsize))
    resource.setrlimit(resource.RLIMIT_NOFILE, (int(cfg.get('open_files', 64)),) * 2)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def main(argv: list[str]) -> None:
    if argv[1:2] == ['--probe']:
        cfg = json.loads(argv[2]) if len(argv) > 2 else {'read': [], 'exec': []}
        abi = apply_landlock(cfg.get('read', []), cfg.get('exec', []))
        ok = apply_seccomp()
        print(json.dumps({'landlock': abi, 'seccomp': ok}))
        return
    cfg = json.loads(argv[1])
    os.chdir(cfg['workdir'])
    apply_rlimits(cfg)
    layers = {'landlock': apply_landlock(cfg['read'], cfg['exec']), 'seccomp': apply_seccomp()}
    if cfg.get('require_kernel') and not (layers['landlock'] and layers['seccomp']):
        sys.stderr.write('sandbox: kernel isolation unavailable\n')
        os._exit(97)
    os.execve(cfg['argv'][0], cfg['argv'], cfg.get('env', {}))


if __name__ == '__main__':
    main(sys.argv)
