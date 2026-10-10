"""Выгрузка спецификации OpenAPI в docs/openapi.json — та же, что отдаёт /openapi.json.

PYTHONPATH=src python scripts/export_openapi.py
PYTHONPATH=src python scripts/export_openapi.py --check   # код 1, если файл устарел (для CI)
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

os.environ.setdefault('SECRET_KEY', 'openapi-export-only-0123456789abcdef0123456789abcdef')

from app.main import create_app

OUT = Path(__file__).resolve().parent.parent / 'docs' / 'openapi.json'


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='не писать, а проверить актуальность')
    args = ap.parse_args()
    spec = json.dumps(create_app().openapi(), ensure_ascii=False, indent=2) + '\n'
    if args.check:
        if not OUT.exists() or OUT.read_text(encoding='utf-8') != spec:
            print(f'{OUT.name} устарел: PYTHONPATH=src python scripts/export_openapi.py')
            return 1
        return 0
    OUT.write_text(spec, encoding='utf-8')
    paths = json.loads(spec)['paths']
    print(f'{OUT.name}: {len(paths)} путей, {sum(len(v) for v in paths.values())} операций')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
