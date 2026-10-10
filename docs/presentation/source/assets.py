"""Картинки для презентации: аватары команды, QR-код стенда, кадрирование скриншотов."""

import os
import sys

import qrcode
from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = sys.argv[1]
SHOTS = sys.argv[2]
REPO_ASSETS = sys.argv[3]
os.makedirs(OUT, exist_ok=True)
FONT = os.path.expanduser('~/.fonts/montserrat/Montserrat-Bold.ttf')

# Аватары: инициалы на градиенте палитры шаблона (фотографий участников нет)
team = [('ЯД', (0x52, 0x09, 0x78), (0xFF, 0x00, 0x53)), ('ИЖ', (0x31, 0x0F, 0x53), (0x8A, 0x83, 0xD1)),
        ('СЕ', (0x52, 0x09, 0x78), (0xFC, 0x37, 0x77)), ('АЖ', (0x31, 0x0F, 0x53), (0xFF, 0x00, 0x53))]
for i, (ini, c1, c2) in enumerate(team, 1):
    W, H = 900, 810
    im = Image.new('RGB', (W, H))
    d = ImageDraw.Draw(im)
    for y in range(H):
        for_t = y / H
        col = tuple(int(c1[k] + (c2[k] - c1[k]) * for_t) for k in range(3))
        d.line([(0, y), (W, y)], fill=col)
    # код-паттерн ФСП: полупрозрачные глифы
    glyphs = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    g = ImageDraw.Draw(glyphs)
    small = ImageFont.truetype(FONT, 60)
    for k, ch in enumerate(['{ }', '</>', '//', '::', '[ ]']):
        g.text((60 + (k * 170) % 760, 40 + (k * 157) % 700), ch, font=small, fill=(255, 255, 255, 40))
    im = Image.alpha_composite(im.convert('RGBA'), glyphs)
    d = ImageDraw.Draw(im)
    big = ImageFont.truetype(FONT, 300)
    bb = d.textbbox((0, 0), ini, font=big)
    d.text(((W - bb[2] - bb[0]) / 2, (H - bb[3] - bb[1]) / 2 - 20), ini, font=big, fill=(255, 255, 255, 255))
    im.convert('RGB').save(f'{OUT}/avatar{i}.png')

# QR-код стенда в цветах шаблона
qr = qrcode.QRCode(border=2, box_size=24, error_correction=qrcode.constants.ERROR_CORRECT_M)
qr.add_data('https://hyrekit.ru/express')
qr.make(fit=True)
qr.make_image(fill_color=(0x31, 0x0F, 0x53), back_color='white').convert('RGB').save(f'{OUT}/qr-express.png')
qr = qrcode.QRCode(border=2, box_size=24, error_correction=qrcode.constants.ERROR_CORRECT_M)
qr.add_data('https://github.com/Fighter90/hyrekit_fsp')
qr.make(fit=True)
qr.make_image(fill_color=(0x31, 0x0F, 0x53), back_color='white').convert('RGB').save(f'{OUT}/qr-repo.png')


def crop(src, dst, box=None, size=None):
    im = Image.open(src).convert('RGB')
    if box:
        w, h = im.size
        im = im.crop((int(box[0] * w), int(box[1] * h), int(box[2] * w), int(box[3] * h)))
    if size:
        im.thumbnail(size, Image.LANCZOS)
    im.save(dst, quality=90)


S = SHOTS
crop(f'{REPO_ASSETS}/landing.png', f'{OUT}/landing.jpg', size=(1920, 1200))
crop(f'{REPO_ASSETS}/express-question.png', f'{OUT}/express-question.jpg', size=(1920, 1200))
crop(f'{REPO_ASSETS}/express-result.png', f'{OUT}/express-result.jpg', size=(1920, 1200))
crop(f'{REPO_ASSETS}/employer-matches.png', f'{OUT}/employer-matches.jpg', size=(1920, 1200))
crop(f'{REPO_ASSETS}/employer-vacancy-test.png', f'{OUT}/employer-vacancy-test.jpg', size=(1920, 1200))
crop(f'{S}/arena-editor.png', f'{OUT}/arena-editor.jpg', size=(1920, 1200))
crop(f'{S}/arena-feedback.png', f'{OUT}/arena-feedback.jpg', box=(0.53, 0.0, 1.0, 1.0), size=(1400, 1500))
crop(f'{S}/arena-board.png', f'{OUT}/arena-board.jpg', box=(0.22, 0.39, 0.93, 0.955), size=(1600, 1400))
crop(f'{S}/arena-showcase.png', f'{OUT}/arena-showcase.jpg', size=(1920, 1200))
for n in ['m-landing', 'm-express', 'm-question', 'm-matches']:
    crop(f'{S}/{n}.png', f'{OUT}/{n}.jpg', size=(780, 1688))
crop(f'{S}/m-fsp-id.png', f'{OUT}/m-fsp-id.jpg', box=(0.0, 0.165, 1.0, 1.0), size=(780, 1688))
print('ok')
