"""Рейтинг Arena по Glicko-2 (Glickman, 2012).

Период рейтинга — одно участие в раунде. Соперники — задачи раунда с
фиксированным рейтингом по уровню (problems.LEVEL_RATING): решил — победа,
не решил — поражение. Неуверенность (RD) растёт при отсутствии: один
период бездействия на каждые INACTIVITY_DAYS дней.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

SCALE = 173.7178
INITIAL_RATING = 1500.0
INITIAL_RD = 350.0
INITIAL_VOLATILITY = 0.06
TAU = 0.5
PROBLEM_RD = 50.0
PROVISIONAL_RD = 110.0  # выше — рейтинг предварительный
MIN_RD = 30.0
INACTIVITY_DAYS = 30
EPS = 1e-6


@dataclass
class Player:
    rating: float = INITIAL_RATING
    rd: float = INITIAL_RD
    volatility: float = INITIAL_VOLATILITY

    @property
    def provisional(self) -> bool:
        return self.rd > PROVISIONAL_RD


def _g(phi: float) -> float:
    return 1.0 / math.sqrt(1.0 + 3.0 * phi**2 / math.pi**2)


def _e(mu: float, mu_j: float, phi_j: float) -> float:
    return 1.0 / (1.0 + math.exp(-_g(phi_j) * (mu - mu_j)))


def inflate(player: Player, idle_days: float) -> Player:
    """Рост неуверенности за время без участия."""
    periods = int(max(0.0, idle_days) // INACTIVITY_DAYS)
    if periods <= 0:
        return player
    phi = player.rd / SCALE
    phi = math.sqrt(phi**2 + periods * player.volatility**2)
    return Player(player.rating, min(INITIAL_RD, phi * SCALE), player.volatility)


def update(player: Player, results: list[tuple[float, float, float]]) -> Player:
    """results: [(рейтинг соперника, RD соперника, исход 1/0.5/0)]."""
    mu = (player.rating - INITIAL_RATING) / SCALE
    phi = player.rd / SCALE
    sigma = player.volatility
    if not results:
        phi_star = math.sqrt(phi**2 + sigma**2)
        return Player(player.rating, min(INITIAL_RD, phi_star * SCALE), sigma)

    opp = [((r - INITIAL_RATING) / SCALE, rd / SCALE, s) for r, rd, s in results]
    v_inv = 0.0
    delta_sum = 0.0
    for mu_j, phi_j, s in opp:
        e = _e(mu, mu_j, phi_j)
        g = _g(phi_j)
        v_inv += g**2 * e * (1 - e)
        delta_sum += g * (s - e)
    v = 1.0 / v_inv
    delta = v * delta_sum

    # Новая волатильность: метод Иллинойса (шаг 5 статьи)
    a = math.log(sigma**2)

    def f(x: float) -> float:
        ex = math.exp(x)
        return ex * (delta**2 - phi**2 - v - ex) / (2 * (phi**2 + v + ex) ** 2) - (x - a) / TAU**2

    big_a = a
    if delta**2 > phi**2 + v:
        big_b = math.log(delta**2 - phi**2 - v)
    else:
        k = 1
        while f(a - k * TAU) < 0:
            k += 1
        big_b = a - k * TAU
    fa, fb = f(big_a), f(big_b)
    while abs(big_b - big_a) > EPS:
        c = big_a + (big_a - big_b) * fa / (fb - fa)
        fc = f(c)
        if fc * fb <= 0:
            big_a, fa = big_b, fb
        else:
            fa /= 2
        big_b, fb = c, fc
    sigma_new = math.exp(big_a / 2)

    phi_star = math.sqrt(phi**2 + sigma_new**2)
    phi_new = 1.0 / math.sqrt(1.0 / phi_star**2 + 1.0 / v)
    mu_new = mu + phi_new**2 * delta_sum
    return Player(
        rating=round(INITIAL_RATING + SCALE * mu_new, 1),
        rd=round(max(MIN_RD, min(INITIAL_RD, SCALE * phi_new)), 1),
        volatility=sigma_new,
    )


def matching_score(rating: float | None, rd: float | None) -> float:
    """Рейтинг Arena в шкале 0..100 для подборки: 1200 → 0, 2000 → 100; предварительный — вдвое меньше."""
    if rating is None:
        return 0.0
    score = max(0.0, min(100.0, (rating - 1200.0) / 8.0))
    if rd is not None and rd > PROVISIONAL_RD:
        score /= 2
    return round(score, 1)
