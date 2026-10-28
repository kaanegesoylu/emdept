"""Ayrık olay simülasyonu: ilk gelen ilk hizmet alır, saat saat değişen hekim çizelgesi.

Muayenesi süren hasta, hekimin vardiyası bitse de yarıda bırakılmaz.
Zamanlar t0'dan (ilk günün 00:00'ı) itibaren saat cinsinden float'tır.
"""
from __future__ import annotations

import math
from typing import Callable, Sequence

import numpy as np


def simulate_fcfs(arrivals: Sequence[float], durations: Sequence[float],
                  c_at: Callable[[int], int], max_c: int) -> np.ndarray:
    """Her hastanın muayeneye alınma zamanını döndürür (saat).

    arrivals artan sırada olmalı. c_at(h): t0'dan itibaren h. saatteki hekim sayısı.
    """
    free = [-math.inf] * max_c
    starts = np.empty(len(arrivals))

    def on_shift(k: int, t: float) -> float:
        h = math.floor(t)
        for _ in range(24 * 14):
            if c_at(h) > k:
                return max(t, float(h))
            h += 1
        return math.inf

    for i, a in enumerate(arrivals):
        best, bk = math.inf, -1
        for k in range(max_c):
            s = on_shift(k, max(a, free[k]))
            if s < best:
                best, bk = s, k
                if s == a:
                    break
        starts[i] = best
        if bk >= 0 and math.isfinite(best):
            free[bk] = best + durations[i]
    return starts


def service_times(rng: np.random.Generator, n: int, mean: float, cv: float) -> np.ndarray:
    """Ortalama `mean`, değişim katsayısı `cv` olan süreler (cv=1 → üstel, diğer → gama)."""
    if abs(cv - 1) < 1e-9:
        return rng.exponential(mean, n)
    k = 1 / cv ** 2
    return rng.gamma(k, mean / k, n)


def validate(lam_h: Sequence[float], svc_mean_min: float, svc_cv: float, schedule: Sequence[int],
             T_min: float, reps: int = 20, days: int = 14, seed: int = 11) -> list[dict]:
    """Aynı saatlik geliş hızlarıyla `reps` tekrar × `days` gün simülasyon (ilk gün ısınma, atılır).

    Döner: her saat için {'mean': ort. bekleme dk, 'within': T içinde oranı, 'n': hasta}.
    """
    rng = np.random.default_rng(seed)
    max_c = max(1, int(max(schedule)))
    tot = np.zeros(24)
    cnt = np.zeros(24)
    inside = np.zeros(24)
    sched = [int(round(c)) for c in schedule]
    for _ in range(reps):
        arr = []
        for d in range(days + 1):
            for h in range(24):
                k = rng.poisson(lam_h[h])
                arr.extend(d * 24 + h + rng.random(k))
        arr = np.sort(np.asarray(arr))
        dur = service_times(rng, len(arr), svc_mean_min / 60, svc_cv)
        st = simulate_fcfs(arr, dur, lambda h: sched[h % 24], max_c)
        keep = arr >= 24
        hours = (np.floor(arr[keep]) % 24).astype(int)
        w = (st[keep] - arr[keep]) * 60
        ok = np.isfinite(w)
        np.add.at(tot, hours[ok], w[ok])
        np.add.at(cnt, hours[ok], 1)
        np.add.at(inside, hours[ok], (w[ok] <= T_min).astype(float))
    return [{"mean": tot[h] / cnt[h] if cnt[h] else math.nan,
             "within": inside[h] / cnt[h] if cnt[h] else math.nan,
             "n": int(cnt[h])} for h in range(24)]
