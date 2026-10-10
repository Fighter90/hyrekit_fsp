"""Стандартизированный PDF-профиль кандидата (единый шаблон для всех)."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.catalog.data import GRADE_TITLES, INDUSTRIES, SPEC_BY_CODE

FONT_DIR = Path(__file__).resolve().parent.parent / 'assets' / 'fonts'
BLUE = colors.HexColor('#402FFF')
RED = colors.HexColor('#EC1D35')
INK = colors.HexColor('#1B1C21')
MUTED = colors.HexColor('#3A3C46')
_fonts_ready = False
FORMATS = {'office': 'офис', 'hybrid': 'гибрид', 'remote': 'удалённо'}


def _fonts() -> None:
    """JetBrains Mono — фирменный шрифт ФСП с кириллицей."""
    global _fonts_ready
    if not _fonts_ready:
        pdfmetrics.registerFont(TTFont('JBM', str(FONT_DIR / 'JetBrainsMono-Regular.ttf')))
        pdfmetrics.registerFont(TTFont('JBM-Bold', str(FONT_DIR / 'JetBrainsMono-Bold.ttf')))
        _fonts_ready = True


def _p(text: Any, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(str(text)).replace('\n', '<br/>'), style)


def render_profile_pdf(profile: dict[str, Any]) -> bytes:
    """profile — словарь в формате CandidateProfileOut."""
    _fonts()
    base = ParagraphStyle('base', fontName='JBM', fontSize=9.5, leading=13, textColor=INK)
    small = ParagraphStyle('small', parent=base, fontSize=8, textColor=MUTED)
    h1 = ParagraphStyle('h1', parent=base, fontName='JBM-Bold', fontSize=18, leading=22)
    h2 = ParagraphStyle(
        'h2', parent=base, fontName='JBM-Bold', fontSize=11, textColor=BLUE, spaceBefore=10, spaceAfter=4
    )
    badge = ParagraphStyle('badge', parent=base, fontName='JBM-Bold', textColor=colors.white)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title='Профиль кандидата HyreKit',
    )
    el: list[Any] = []
    el.append(_p('HYREKIT · ПРОФИЛЬ КАНДИДАТА', small))
    el.append(Spacer(1, 4))
    el.append(_p(profile.get('full_name') or 'Кандидат', h1))
    if profile.get('headline'):
        el.append(_p(profile['headline'], base))
    el.append(Spacer(1, 6))

    spec = SPEC_BY_CODE.get(profile.get('specialization') or '', {}).get('title', '—')
    grade = GRADE_TITLES.get(profile.get('grade') or '', 'не подтверждён')
    cat = profile.get('category_title') or 'Категория не присвоена'
    t = Table([[_p(cat, badge)]], hAlign='LEFT')
    t.setStyle(
        TableStyle(
            [
                ('BACKGROUND', (0, 0), (-1, -1), BLUE),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ]
        )
    )
    el.append(t)

    industries = {i['code']: i['title'] for i in INDUSTRIES}
    rows = [
        ('Специализация', spec),
        ('Подтверждённый грейд', grade),
        ('Результат теста', f"{profile['test_score']:.0f} / 100" if profile.get('test_score') is not None else '—'),
        ('Рейтинг в категории', f"{profile['rating']:.0f} / 100" if profile.get('rating') is not None else '—'),
        ('Стаж', f"{profile['experience_years']:g} лет" if profile.get('experience_years') is not None else '—'),
        ('Отрасль', industries.get(profile.get('industry') or '', '—')),
        ('Город', profile.get('city') or '—'),
        ('Формат работы', FORMATS.get(profile.get('work_format') or '', '—')),
    ]
    if profile.get('salary_from') or profile.get('salary_to'):
        rows.append(('Ожидания, ₽', f"{profile.get('salary_from') or '…'} – {profile.get('salary_to') or '…'}"))
    el.append(_p('Ключевые данные', h2))
    info = Table([[_p(k, small), _p(v, base)] for k, v in rows], colWidths=[50 * mm, None], hAlign='LEFT')
    info.setStyle(
        TableStyle(
            [('LINEBELOW', (0, 0), (-1, -1), 0.25, colors.HexColor('#D9D9D9')), ('VALIGN', (0, 0), (-1, -1), 'TOP')]
        )
    )
    el.append(info)

    for title, key in (('Стек', 'stack'), ('Роли в команде', 'roles'), ('Софт-скиллы', 'soft_skills')):
        if profile.get(key):
            el.append(_p(title, h2))
            el.append(_p(' · '.join(profile[key]), base))
    if profile.get('about'):
        el.append(_p('О себе', h2))
        el.append(_p(profile['about'], base))

    el.append(_p('Достижения ФСП', h2))
    fsp = profile.get('fsp')
    if fsp and fsp.get('has_history'):
        for a in fsp['achievements']:
            place = f", {a['place']} место" if a.get('place') else ', участие'
            el.append(_p(f"▲ {a['year']} — {a['event']} ({a['discipline']}{place})", base))
        el.append(_p(f"Балл ФСП: {fsp['score']} / 100 · ФСП ID {fsp['fsp_id']}", small))
    else:
        el.append(_p('История участия в соревнованиях ФСП отсутствует.', small))

    contacts = [c for c in (profile.get('contact_email'), profile.get('phone'), profile.get('telegram')) if c]
    if contacts:
        el.append(_p('Контакты', h2))
        el.append(_p(' · '.join(contacts), base))
    el.append(Spacer(1, 14))
    el.append(_p('Категория присвоена по итогам опроса и тестирования на платформе HyreKit.', small))
    doc.build(el)
    return buf.getvalue()
