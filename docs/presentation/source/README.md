# Сборка презентации

Презентация собирается из официального шаблона ФСП «ЛЦТ 2026» (`ЛЦТ_2026_Шаблон презентации ФСП.pptx`, выдаётся организаторами): скрипт заполняет слайды шаблона текстом, скриншотами и диаграммами и оставляет 23 слайда в порядке питча.

```bash
pip install python-pptx pillow qrcode
cd docs/presentation/source
python3 assets.py img ../assets ../assets          # аватары, QR-коды, кадрирование скриншотов
python3 build.py "<путь к шаблону>.pptx" img full.pptx
python3 compress.py full.pptx ../HyreKit_pitch.pptx  # фоны шаблона 4K → 2560 px, иначе файл весит 14 МБ
soffice --headless --convert-to pdf --outdir .. ../HyreKit_pitch.pptx
```

Нужен шрифт Montserrat. Числа на слайдах взяты из `src/app/assessment/engine.py`, `src/app/matching/service.py`, `docs/validation/results.md` и `docs/validation/load.md`; при их изменении поправьте `build.py` и пересоберите.
