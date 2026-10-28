"""Sentetik yeşil alan verisi üreteci.

Hastane verisi gelene kadar sistemin çalışması için kullanılır. Varsayılan değerler
örnek varsayımdır; hastaneden alınmış rakamlar değildir.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd

from .simulation import simulate_fcfs, service_times

# Saatlik göreli geliş ağırlıkları (00..23)
PROFILES: dict[str, list[float]] = {
    # Durmuş (2009): yoğunluk 16–24 saatleri arasında
    "aksam": [2.4, 2.0, 1.6, 1.3, 1.1, 1.1, 1.4, 2.0, 3.2, 4.2, 4.6, 4.6,
              4.4, 4.4, 4.6, 5.0, 5.8, 6.4, 6.8, 7.0, 7.0, 6.6, 5.6, 4.0],
    "gunduz": [1.2, 1.0, 0.8, 0.7, 0.7, 0.8, 1.2, 2.4, 4.6, 6.2, 6.8, 6.8,
               6.2, 6.0, 6.2, 6.4, 6.0, 5.4, 4.8, 4.2, 3.6, 3.0, 2.2, 1.6],
    "duz": [1.0] * 24,
}
PROFILE_LABELS = {"aksam": "Akşam yoğun (16–24)", "gunduz": "Gündüz yoğun", "duz": "Düz"}

DEFAULT_STAFFING = [1] * 8 + [2] * 16


@dataclass
class GeneratorParams:
    start_date: str = "2026-01-05"
    days: int = 28
    daily: float = 110
    profile: str = "aksam"
    monday_factor: float = 1.15
    weekend_factor: float = 1.10
    service_min: float = 12
    service_cv: float = 1.0
    test_prob: float = 0.35      # tetkik istenme olasılığı (çıkışı geciktirir)
    test_min: float = 55
    dispersion: float = 0.0      # günlük dalgalanma CV'si; 0 = saf Poisson
    seed: int = 497

    def to_dict(self) -> dict:
        return asdict(self)


def hourly_rates(profile: str, daily: float) -> np.ndarray:
    w = np.asarray(PROFILES.get(profile, PROFILES["aksam"]), dtype=float)
    return daily * w / w.sum()


def generate(p: GeneratorParams, staffing: list[int]) -> pd.DataFrame:
    """Kolonlar: arrival, start, end, exit (pandas Timestamp)."""
    rng = np.random.default_rng(p.seed)
    t0 = pd.Timestamp(p.start_date)
    base = hourly_rates(p.profile, p.daily)
    arr: list[float] = []
    for d in range(p.days):
        dow = (t0 + pd.Timedelta(days=d)).dayofweek  # 0 = pazartesi
        f = 1.0
        if dow == 0:
            f *= p.monday_factor
        if dow >= 5:
            f *= p.weekend_factor
        if p.dispersion > 0:
            k = 1 / p.dispersion ** 2
            f *= rng.gamma(k, 1 / k)
        for h in range(24):
            n = rng.poisson(base[h] * f)
            arr.extend(d * 24 + h + rng.random(n))
    a = np.sort(np.asarray(arr))
    dur = service_times(rng, len(a), p.service_min / 60, p.service_cv)
    sched = [int(c) for c in staffing]
    s = simulate_fcfs(a, dur, lambda h: sched[h % 24], max(1, max(sched)))
    e = s + dur
    has_test = rng.random(len(a)) < p.test_prob
    extra = np.where(has_test, service_times(rng, len(a), p.test_min / 60, 0.8),
                     (2 + 6 * rng.random(len(a))) / 60)
    x = e + extra
    to_ts = lambda v: t0 + pd.to_timedelta(np.round(v * 3600), unit="s")
    return pd.DataFrame({"arrival": to_ts(a), "start": to_ts(s), "end": to_ts(e), "exit": to_ts(x)})
