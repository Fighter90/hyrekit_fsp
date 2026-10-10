"""Справочник HyreKit.

На этапе MVP справочник статический: основные направления ИТ и общепринятая
лестница грейдов. Коды стабильны и используются как ключи категорий
(`backend:middle`), поэтому меняются только вместе с миграцией данных.
"""

from __future__ import annotations

from typing import Final

GRADE_COOLDOWN_DAYS: Final = 90  # смена грейда не чаще раза в 3 месяца

GRADES: Final[list[dict]] = [
    {'code': 'intern', 'title': 'Intern', 'order': 0, 'years': 'без опыта'},
    {'code': 'junior', 'title': 'Junior', 'order': 1, 'years': 'до 1–2 лет'},
    {'code': 'middle', 'title': 'Middle', 'order': 2, 'years': '2–4 года'},
    {'code': 'senior', 'title': 'Senior', 'order': 3, 'years': '4–7 лет'},
    {'code': 'lead', 'title': 'Lead', 'order': 4, 'years': '7+ лет'},
]
GRADE_CODES: Final = [g['code'] for g in GRADES]
GRADE_ORDER: Final = {g['code']: g['order'] for g in GRADES}
GRADE_TITLES: Final = {g['code']: g['title'] for g in GRADES}

SPECIALIZATIONS: Final[list[dict]] = [
    {
        'code': 'backend',
        'title': 'Backend',
        'topics': ['algorithms', 'python', 'sql', 'http', 'architecture'],
        'stack_hints': ['Python', 'Go', 'Java', 'PostgreSQL', 'FastAPI', 'Django', 'Redis', 'Kafka'],
        'fsp_disciplines': ['продуктовое программирование', 'алгоритмическое программирование'],
    },
    {
        'code': 'frontend',
        'title': 'Frontend',
        'topics': ['algorithms', 'javascript', 'web', 'http', 'architecture'],
        'stack_hints': ['TypeScript', 'React', 'Vue', 'Next.js', 'CSS', 'Vite'],
        'fsp_disciplines': ['продуктовое программирование'],
    },
    {
        'code': 'data',
        'title': 'Data Science / ML',
        'topics': ['algorithms', 'python', 'sql', 'ml', 'statistics'],
        'stack_hints': ['Python', 'Pandas', 'PyTorch', 'scikit-learn', 'SQL', 'Spark'],
        'fsp_disciplines': ['алгоритмическое программирование', 'программирование беспилотных систем'],
    },
    {
        'code': 'devops',
        'title': 'DevOps / SRE',
        'topics': ['linux', 'networks', 'containers', 'http', 'architecture'],
        'stack_hints': ['Linux', 'Docker', 'Kubernetes', 'Terraform', 'Ansible', 'Prometheus'],
        'fsp_disciplines': ['информационная безопасность', 'продуктовое программирование'],
    },
    {
        'code': 'qa',
        'title': 'QA / Тестирование',
        'topics': ['testing', 'sql', 'http', 'python', 'algorithms'],
        'stack_hints': ['Pytest', 'Selenium', 'Playwright', 'Postman', 'SQL', 'Allure'],
        'fsp_disciplines': ['продуктовое программирование'],
    },
    {
        'code': 'security',
        'title': 'Информационная безопасность',
        'topics': ['networks', 'linux', 'security', 'http', 'algorithms'],
        'stack_hints': ['Linux', 'Burp Suite', 'Wireshark', 'Python', 'SIEM'],
        'fsp_disciplines': ['информационная безопасность'],
    },
]
TOPIC_TITLES: Final = {
    'algorithms': 'Алгоритмы',
    'python': 'Python',
    'javascript': 'JavaScript',
    'web': 'Веб и браузер',
    'http': 'HTTP и API',
    'sql': 'SQL и базы данных',
    'architecture': 'Архитектура',
    'ml': 'Машинное обучение',
    'statistics': 'Статистика',
    'linux': 'Linux',
    'networks': 'Сети',
    'containers': 'Контейнеры',
    'testing': 'Тестирование',
    'security': 'Безопасность',
}

# Какую тему теста подтверждает технология из стека вакансии (ключи — в нижнем регистре).
TECH_TOPICS: Final = {
    'python': 'python',
    'django': 'python',
    'fastapi': 'python',
    'flask': 'python',
    'pandas': 'python',
    'postgresql': 'sql',
    'sql': 'sql',
    'mysql': 'sql',
    'clickhouse': 'sql',
    'oracle': 'sql',
    'javascript': 'javascript',
    'typescript': 'javascript',
    'node.js': 'javascript',
    'react': 'web',
    'vue': 'web',
    'next.js': 'web',
    'css': 'web',
    'html': 'web',
    'vite': 'web',
    'docker': 'containers',
    'kubernetes': 'containers',
    'helm': 'containers',
    'linux': 'linux',
    'bash': 'linux',
    'ansible': 'linux',
    'kafka': 'architecture',
    'redis': 'architecture',
    'rabbitmq': 'architecture',
    'grpc': 'http',
    'rest': 'http',
    'graphql': 'http',
    'nginx': 'http',
    'pytorch': 'ml',
    'scikit-learn': 'ml',
    'tensorflow': 'ml',
    'spark': 'statistics',
    'pytest': 'testing',
    'selenium': 'testing',
    'playwright': 'testing',
    'postman': 'testing',
    'allure': 'testing',
    'wireshark': 'networks',
    'burp suite': 'security',
    'siem': 'security',
    'prometheus': 'linux',
}

SPEC_CODES: Final = [s['code'] for s in SPECIALIZATIONS]
SPEC_BY_CODE: Final = {s['code']: s for s in SPECIALIZATIONS}

INDUSTRIES: Final[list[dict]] = [
    {'code': 'fintech', 'title': 'Финтех и банки'},
    {'code': 'ecommerce', 'title': 'E-commerce и ритейл'},
    {'code': 'gov', 'title': 'Госсектор'},
    {'code': 'telecom', 'title': 'Телеком'},
    {'code': 'industry', 'title': 'Промышленность'},
    {'code': 'edtech', 'title': 'Образование'},
    {'code': 'gamedev', 'title': 'Игры'},
    {'code': 'it_services', 'title': 'ИТ-услуги и аутсорс'},
    {'code': 'other', 'title': 'Другое'},
]
INDUSTRY_CODES: Final = [i['code'] for i in INDUSTRIES]

WORK_FORMATS: Final[list[dict]] = [
    {'code': 'office', 'title': 'Офис'},
    {'code': 'hybrid', 'title': 'Гибрид'},
    {'code': 'remote', 'title': 'Удалённо'},
]


def category_code(specialization: str, grade: str) -> str:
    return f'{specialization}:{grade}'


def category_title(specialization: str | None, grade: str | None) -> str | None:
    if not specialization or not grade:
        return None
    spec = SPEC_BY_CODE.get(specialization, {}).get('title', specialization)
    return f'{spec} · {GRADE_TITLES.get(grade, grade)}'


def public_catalog() -> dict:
    return {
        'specializations': [
            {'code': s['code'], 'title': s['title'], 'topics': s['topics'], 'stack_hints': s['stack_hints']}
            for s in SPECIALIZATIONS
        ],
        'grades': GRADES,
        'industries': INDUSTRIES,
        'work_formats': WORK_FORMATS,
        'grade_change_cooldown_days': GRADE_COOLDOWN_DAYS,
    }
