"""Автораспознавание резюме: ФИО, контакты, стек, грейд, роли, стаж, софт-скиллы.

Двухступенчатая схема: детерминированные правила (регулярные выражения и
словарь технологий) работают всегда, а при настроенном GigaChat модель
уточняет поля. Ответ LLM проходит ту же валидацию, что и ручной ввод.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import Any

from app.catalog.data import GRADE_CODES, SPEC_CODES
from app.llm.gigachat import get_llm

logger = logging.getLogger(__name__)

TECH = [
    'Python',
    'Go',
    'Java',
    'Kotlin',
    'C++',
    'C#',
    'Rust',
    'PHP',
    'Ruby',
    'Scala',
    'Swift',
    'JavaScript',
    'TypeScript',
    'React',
    'Vue',
    'Angular',
    'Next.js',
    'Node.js',
    'Svelte',
    'Redux',
    'HTML',
    'CSS',
    'SASS',
    'Webpack',
    'Vite',
    'Django',
    'FastAPI',
    'Flask',
    'Spring',
    'Laravel',
    '.NET',
    'PostgreSQL',
    'MySQL',
    'MongoDB',
    'Redis',
    'ClickHouse',
    'Elasticsearch',
    'Kafka',
    'RabbitMQ',
    'SQL',
    'Docker',
    'Kubernetes',
    'Terraform',
    'Ansible',
    'Linux',
    'Nginx',
    'Prometheus',
    'Grafana',
    'GitLab CI',
    'AWS',
    'Yandex Cloud',
    'Git',
    'Pandas',
    'NumPy',
    'PyTorch',
    'TensorFlow',
    'scikit-learn',
    'Spark',
    'Airflow',
    'MLflow',
    'Selenium',
    'Playwright',
    'Pytest',
    'Postman',
    'JMeter',
    'Allure',
    'Burp Suite',
    'Wireshark',
    'SIEM',
    'Kali',
]
SOFT = {
    'коммуникаб': 'Коммуникабельность',
    'команд': 'Работа в команде',
    'лидер': 'Лидерство',
    'ответствен': 'Ответственность',
    'самостоятель': 'Самостоятельность',
    'наставни': 'Наставничество',
    'менторств': 'Наставничество',
    'аналитическ': 'Аналитическое мышление',
    'обучаем': 'Обучаемость',
    'тайм-менедж': 'Тайм-менеджмент',
    'презентац': 'Публичные выступления',
}
ROLES = {
    'тимлид': 'Тимлид',
    'team lead': 'Тимлид',
    'архитект': 'Архитектор',
    'backend': 'Backend-разработчик',
    'бэкенд': 'Backend-разработчик',
    'frontend': 'Frontend-разработчик',
    'фронтенд': 'Frontend-разработчик',
    'fullstack': 'Fullstack-разработчик',
    'devops': 'DevOps-инженер',
    'тестировщ': 'QA-инженер',
    'qa': 'QA-инженер',
    'data scien': 'Data Scientist',
    'аналитик': 'Аналитик',
    'ml': 'ML-инженер',
}
SPEC_HINTS = [
    ('frontend', ['frontend', 'фронтенд', 'react', 'vue', 'angular']),
    ('data', ['data scien', 'machine learning', 'ml-инженер', 'pytorch', 'pandas']),
    ('devops', ['devops', 'sre', 'kubernetes', 'terraform']),
    ('qa', ['тестировщ', 'qa', 'автотест', 'selenium']),
    ('security', ['пентест', 'безопасност', 'siem', 'security']),
    ('backend', ['backend', 'бэкенд', 'django', 'fastapi', 'spring', 'golang']),
]

EMAIL_RE = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')
PHONE_RE = re.compile(r'(?:\+7|8)[\s(-]*\d{3}[\s)-]*\d{3}[\s-]*\d{2}[\s-]*\d{2}')
TG_RE = re.compile(r'(?:t\.me/|telegram[:\s]+|tg[:\s]+)@?([A-Za-z0-9_]{4,32})', re.I)
YEARS_RE = re.compile(r'(?:опыт[^\n\d]{0,30})(\d{1,2}(?:[.,]\d)?)\s*(?:год|лет)', re.I)
RANGE_RE = re.compile(r'((?:19|20)\d{2})\s*[-–—]\s*((?:19|20)\d{2}|н\.?\s*в\.?|наст|сейчас|по настоящее)', re.I)
NAME_RE = re.compile(r'^([А-ЯЁ][а-яё]+(?:-[А-ЯЁ][а-яё]+)?)\s+([А-ЯЁ][а-яё]+)(?:\s+([А-ЯЁ][а-яё]+))?$')
CITY_RE = re.compile(r'(?:город|г\.|проживание|location)[:\s]+([А-ЯЁA-Z][а-яёa-z-]+)', re.I)

PARSE_PROMPT = (
    'Ты извлекаешь данные из резюме ИТ-специалиста. Верни строго JSON с полями: '
    'full_name, city, phone, contact_email, telegram, headline, about (2-3 предложения), '
    'specialization (одно из: ' + ', '.join(SPEC_CODES) + '), '
    'declared_grade (одно из: ' + ', '.join(GRADE_CODES) + '), experience_years (число), '
    'stack (массив технологий), roles (массив ролей), soft_skills (массив). '
    'Если данных нет — null. Ничего не выдумывай.'
)


def _experience(text: str) -> float | None:
    m = YEARS_RE.search(text)
    if m:
        return float(m.group(1).replace(',', '.'))
    now = datetime.now(UTC).year
    spans = []
    for a, b in RANGE_RE.findall(text):
        end = int(b) if b[:2] in ('19', '20') and b.isdigit() else now
        start = int(a)
        if start <= end <= now:
            spans.append((start, end))
    if not spans:
        return None
    return float(max(e for _, e in spans) - min(s for s, _ in spans))


def _grade_from(text: str, years: float | None) -> str | None:
    low = text.lower()
    for g in ('lead', 'senior', 'middle', 'junior', 'intern'):
        if re.search(rf'\b{g}\b', low):
            return g
    if 'стажер' in low or 'стажёр' in low:
        return 'intern'
    if years is None:
        return None
    return 'junior' if years < 2 else 'middle' if years < 4 else 'senior' if years < 7 else 'lead'


def parse_rules(text: str) -> dict[str, Any]:
    """Извлечение полей правилами (без сети)."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    low = text.lower()
    fields: dict[str, Any] = {}
    for ln in lines[:8]:
        m = NAME_RE.match(ln)
        if m:
            fields['full_name'] = ln
            break
    if m := EMAIL_RE.search(text):
        fields['contact_email'] = m.group(0)
    if m := PHONE_RE.search(text):
        fields['phone'] = re.sub(r'[^\d+]', '', m.group(0))
    if m := TG_RE.search(text):
        fields['telegram'] = '@' + m.group(1)
    if m := CITY_RE.search(text):
        fields['city'] = m.group(1)
    stack = [t for t in TECH if re.search(rf'(?<![\w+#.]){re.escape(t.lower())}(?![\w+#])', low)]
    if stack:
        fields['stack'] = stack
    soft = sorted({v for k, v in SOFT.items() if k in low})
    if soft:
        fields['soft_skills'] = soft
    roles = sorted({v for k, v in ROLES.items() if re.search(rf'\b{re.escape(k)}', low)})
    if roles:
        fields['roles'] = roles
    years = _experience(text)
    if years is not None:
        fields['experience_years'] = years
    for spec, hints in SPEC_HINTS:
        if any(h in low for h in hints):
            fields['specialization'] = spec
            break
    if grade := _grade_from(text, years):
        fields['declared_grade'] = grade
    return fields


def _clean_llm(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in ('full_name', 'city', 'phone', 'contact_email', 'telegram', 'headline', 'about'):
        v = data.get(key)
        if isinstance(v, str) and v.strip():
            out[key] = v.strip()[:500]
    for key in ('stack', 'roles', 'soft_skills'):
        v = data.get(key)
        if isinstance(v, list):
            out[key] = [str(x).strip()[:60] for x in v if str(x).strip()][:30]
    if data.get('specialization') in SPEC_CODES:
        out['specialization'] = data['specialization']
    if data.get('declared_grade') in GRADE_CODES:
        out['declared_grade'] = data['declared_grade']
    try:
        if data.get('experience_years') is not None:
            out['experience_years'] = max(0.0, min(60.0, float(data['experience_years'])))
    except (TypeError, ValueError):
        pass
    return out


async def parse_resume_text(text: str) -> tuple[dict[str, Any], str]:
    """Возвращает (поля, источник). GigaChat дополняет правила, если настроен."""
    fields = parse_rules(text)
    llm = get_llm()
    if not llm.is_configured:
        return fields, 'rules'
    try:
        data = await llm.complete_json(system=PARSE_PROMPT, user=text[:12000])
    except Exception:
        logger.warning('LLM не смогла разобрать резюме, используем правила', exc_info=True)
        return fields, 'rules'
    merged = {**fields, **_clean_llm(data)}
    if fields.get('stack') and merged.get('stack'):
        merged['stack'] = list(dict.fromkeys([*merged['stack'], *fields['stack']]))
    return merged, getattr(llm, 'provider', None) or 'gigachat'
