"""Калибровка заданий и мониторинг утечек (FSP-33).

Пересчитывает статистику семейств по завершённым попыткам за окно, пишет
статусы в таблицу `item_calibration` (семейства со статусом «утечка»
исключаются из выдачи) и печатает отчёт для команды. Приложение запускает
то же самое по расписанию (`CALIBRATION_INTERVAL_MINUTES`).

    PYTHONPATH=src python scripts/calibrate.py                      # база из DATABASE_URL
    PYTHONPATH=src python scripts/calibrate.py --dry-run --days 30 --out calibration.md
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime
from pathlib import Path

from app.assessment import calibration
from app.assessment.service import recalibrate
from app.core.database import get_session_factory


def report(stats: list[calibration.FamilyStat], days: int) -> str:
    leaks = [s for s in stats if s.status == 'leak']
    lines = [
        f'# Статус семейств заданий — {datetime.now(UTC):%Y-%m-%d %H:%M} UTC',
        '',
        f'Окно — {days} дней, ответов — {sum(s.shows for s in stats)}, семейств — {len(stats)}. '
        f'Утечка — дрейф выше {calibration.DRIFT_THRESHOLD:.0%} и z выше {calibration.Z_THRESHOLD:g} '
        f'при не меньше чем {calibration.MIN_SHOWS} показах. Методика — `src/app/assessment/calibration.py`.',
        '',
        f'Исключено из выдачи: {", ".join(s.family for s in leaks) if leaks else "нет"}.',
        '',
        '| Семейство | Тема | Показов | Верно | Ожидалось | Дрейф | z | Сдвиг b | Статус |',
        '| -- | -- | --: | --: | --: | --: | --: | --: | -- |',
    ]
    for s in stats:
        lines.append(
            f'| {s.family}{" *" if s.conceptual else ""} | {s.topic} | {s.shows} | {s.solve_rate:.0%} '
            f'| {s.expected_rate:.0%} | {s.drift:+.0%} | {s.z:+.1f} | {s.offset:+.2f} '
            f'| {calibration.STATUS_TITLES[s.status]} |'
        )
    lines += ['', '\\* концептуальное семейство.']
    return '\n'.join(lines) + '\n'


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--days', type=int, default=calibration.WINDOW_DAYS, help='окно наблюдений, дней')
    ap.add_argument('--dry-run', action='store_true', help='не записывать статусы в базу')
    ap.add_argument('--out', help='куда записать отчёт в Markdown')
    args = ap.parse_args()
    async with get_session_factory()() as session:
        stats = await recalibrate(session, window_days=args.days)
        if args.dry_run:
            await session.rollback()
        else:
            await session.commit()
    text = report(stats, args.days)
    print(text)
    if args.out:
        Path(args.out).write_text(text, encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
