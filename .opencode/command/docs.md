---
description: Пересобрать производные документы — openapi.json, docx и pdf, результаты валидации
---
Обнови производные артефакты HyreKit после изменений $ARGUMENTS:

1. API менялся — `PYTHONPATH=src python scripts/export_openapi.py`.
2. Менялась методика или банк заданий — `PYTHONPATH=src python scripts/validate.py`, затем цифры из `docs/validation/results.md` перенеси в `docs/guide/03-metodika-ocenki.md`.
3. Менялись схемы mermaid — `node scripts/render_diagrams.cjs`.
4. Менялся `docs/guide/` — `python scripts/build_docs.py` (нужны pandoc и LibreOffice).

Покажи, какие файлы изменились (`git status --short`), и проверь ссылки в изменённых Markdown-файлах.
