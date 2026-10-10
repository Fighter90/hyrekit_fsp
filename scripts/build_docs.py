"""Сборка сопроводительной документации в один docx и pdf (ТЗ, п. 3.4).

Источник — Markdown-разделы docs/guide/ в порядке оглавления. Схемы mermaid заменяются картинками
из docs/assets/diagrams/ (их рисует scripts/render_diagrams.cjs), ссылки на файлы репозитория
ведут на GitHub. Нужны pandoc и LibreOffice (для pdf).

    python scripts/build_docs.py              # docs/HyreKit_Documentation.docx и .pdf
    python scripts/build_docs.py --no-pdf     # только docx
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GUIDE = ROOT / 'docs' / 'guide'
DIAGRAMS = ROOT / 'docs' / 'assets' / 'diagrams'
OUT = ROOT / 'docs' / 'HyreKit_Documentation'
REPO = 'https://github.com/Fighter90/hyrekit_fsp/blob/main/'
ORDER = [
    'README.md',
    '01-produkt.md',
    '02-kak-rabotaet.md',
    '03-metodika-ocenki.md',
    '04-arhitektura.md',
    '05-zapusk-i-demo.md',
    '06-tehnologii-i-servisy.md',
    '07-komanda-i-process.md',
]
LINK = re.compile(r'\]\((?!https?://|#|mailto:)([^)\s]+)\)')
MERMAID = re.compile(r'```mermaid\n.*?```', re.S)


def anchor(md: Path) -> str:
    """Явный якорь раздела: первому заголовку файла присваивается id sec-<имя файла>."""
    return f'#sec-{md.stem.lower()}'


def prepare(md: Path, anchors: dict[str, str]) -> str:
    text = md.read_text(encoding='utf-8')
    counter = iter(range(1, 100))

    def diagram(_: re.Match[str]) -> str:
        png = DIAGRAMS / f'{md.stem}-{next(counter)}.png'
        return f'![]({png.as_posix()})' if png.exists() else _.group(0)

    def link(m: re.Match[str]) -> str:
        target, _, frag = m.group(1).partition('#')
        if target in anchors:  # ссылка на другой раздел руководства — внутри документа
            return f']({"#" + frag if frag else anchors[target]})'
        resolved = (md.parent / target).resolve()
        try:
            rel = resolved.relative_to(ROOT).as_posix()
        except ValueError:
            return m.group(0)
        return f']({REPO}{rel}{"#" + frag if frag else ""})'

    text = re.sub(r'^# (.+)$', lambda _: f'# {title_of(md)} {{{anchor(md)}}}', text, count=1, flags=re.M)
    # картинки схем подставляются после ссылок: локальный путь к PNG не должен уйти на GitHub
    return MERMAID.sub(diagram, LINK.sub(link, text))


def title_of(md: Path) -> str:
    # вводная страница руководства в общем документе — «Введение»: название уже на титуле
    if md.name == 'README.md':
        return 'Введение'
    return next(line[2:] for line in md.read_text(encoding='utf-8').splitlines() if line.startswith('# '))


def contents(files: list[Path]) -> str:
    """Оглавление разделов ссылками: поле TOC из pandoc LibreOffice при конвертации в pdf не заполняет."""
    lines = ['# Содержание {.unnumbered .unlisted}', '']
    for f in files:
        title = title_of(f)
        lines.append(f'- [{title}]({anchor(f)})')
    return '\n'.join(lines) + '\n\n'


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--no-pdf', action='store_true')
    args = ap.parse_args()
    if not shutil.which('pandoc'):
        print('Нужен pandoc: https://pandoc.org/installing.html', file=sys.stderr)
        return 1

    files = [GUIDE / name for name in ORDER]
    anchors = {f.name: anchor(f) for f in files}
    meta = (
        '---\n'
        'title: HyreKit\n'
        'subtitle: Сопроводительная документация · хакатон ФСП 2026, «Команда 1»\n'
        f'date: {datetime.now(UTC):%d.%m.%Y}\n'
        'lang: ru-RU\n'
        '---\n\n'
    )
    body = meta + contents(files) + '\n\n'.join(prepare(f, anchors) for f in files)

    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / 'doc.md'
        src.write_text(body, encoding='utf-8')
        docx = OUT.with_suffix('.docx')
        subprocess.run(  # noqa: S603
            ['pandoc', str(src), '-o', str(docx), f'--resource-path={ROOT}'],  # noqa: S607
            check=True,
        )
        print(docx.relative_to(ROOT))
        if not args.no_pdf:
            office = shutil.which('soffice') or shutil.which('libreoffice')
            if not office:
                print('Для pdf нужен LibreOffice; docx собран', file=sys.stderr)
                return 1
            subprocess.run(  # noqa: S603
                [office, '--headless', '--convert-to', 'pdf', '--outdir', str(OUT.parent), str(docx)],
                check=True,
                capture_output=True,
            )
            print(OUT.with_suffix('.pdf').relative_to(ROOT))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
