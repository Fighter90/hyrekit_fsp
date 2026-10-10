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

## Демо-видео

`video/video.cjs` проходит сценарий в Chromium через Playwright и пишет два ролика (кандидат и работодатель); ffmpeg склеивает их в `../HyreKit_demo.mp4`. Нужен стенд со SQLite: скрипт берёт из базы верные ответы теста (`video/answers.py`) и эталоны задач Arena (`video/refs.py`), чтобы показать сданный тест и вердикт OK.

```bash
node video/video.cjs http://localhost:4173 rec <путь к .db стенда>   # CHROME_PATH — свой Chromium, если нужно
ffmpeg -i rec/page@*.webm -i rec/emp/page@*.webm \
  -filter_complex "[0:v]fps=25,setsar=1[a];[1:v]fps=25,setsar=1[b];[a][b]concat=n=2:v=1[v]" \
  -map "[v]" -c:v libx264 -crf 26 -preset slow -pix_fmt yuv420p -movflags +faststart ../HyreKit_demo.mp4
```

Для входа через ФСП ID на локальном стенде задайте `PUBLIC_URL` адресом фронтенда, иначе тестовый провайдер вернёт браузер на другой порт.
