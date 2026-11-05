"""Varış anındaki bekleme: şu anki kuyruktan başlayıp geleceğe doğru simülasyon.

Kural (yol süresi boyunca yoğunluğun değişmesi):
  Bir hastanın τ dakika sonra hastaneye vardığını düşünelim. Onun beklemesi, kendisinden önce
  gelmiş herkesin (şu an kuyrukta olanlar + yolda geçen τ dakikada gelecek olanlar) muayeneye
  alınmasına bağlıdır. Şu anki kuyruk bilinir (HBYS varsayımı); yolda gelecek hastalar bilinmez,
  bu yüzden geçmişten öğrenilen saatlik geliş hızıyla Poisson olarak üretilir. Hekim sayısı saat
  saat çizelgeden gelir. Bu ileri simülasyon R kez tekrarlanır ve varıştaki beklemenin %25/%50/%75
  yüzdelikleri verilir.

Sonuç olarak:
  - τ kısa ise tahmin büyük ölçüde şu anki kuyruğa dayanır.
  - τ uzadıkça şu anki kuyruğun etkisi erir, varış saatinin geçmiş örüntüsü baskın olur.
  - Belirsizlik τ ile birlikte büyür (aralık genişler).
FCFS'te bir hastanın beklemesi yalnızca kendisinden önce gelenlere bağlı olduğu için, her τ için
"sanal" bir hasta eklemek diğer hastaları etkilemez; tüm varış anları tek simülasyonda hesaplanır.
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Sequence

import numpy as np

from .simulation import service_times

QUANTILES = (0.25, 0.50, 0.75)


def forecast_curve(now: datetime, waiting: int, in_service: int, doctors_now: int,
                   lam_h: Sequence[float], staffing: Sequence[int], svc_mean_min: float, svc_cv: float = 1.0,
                   offsets_min: Sequence[float] = tuple(range(0, 361, 15)), reps: int = 300,
                   seed: int = 0) -> list[dict]:
    """Her varış gecikmesi (dakika) için bekleme yüzdelikleri.

    now: şimdiki an (saat dilimi için), waiting/in_service/doctors_now: anlık kuyruk durumu,
    lam_h: saatlik geliş hızı (24), staffing: saatlik hekim çizelgesi (24).
    Döner: [{"dakika": τ, "alt": .., "orta": .., "ust": ..}, ...] (dakika cinsinden).
    """
    rng = np.random.default_rng(seed)
    offs = np.asarray(sorted(offsets_min), dtype=float) / 60.0         # saat
    horizon = float(offs.max())
    h0 = now.hour + now.minute / 60 + now.second / 3600                # günün saati (ondalık)
    mu_mean = svc_mean_min / 60
    max_c = max(1, int(max(max(staffing), doctors_now)))
    out = np.full((reps, len(offs)), np.nan)

    def c_at(t: float) -> int:
        """t saat sonra görevdeki hekim: bu saat diliminde anlık sayı, sonrası çizelge."""
        if math.floor(h0 + t) == math.floor(h0):
            return doctors_now
        return int(staffing[int(math.floor(h0 + t)) % 24])

    def on_shift(k: int, t: float) -> float:
        """k. hekimin t'den sonra ilk çalışabileceği an."""
        for _ in range(24 * 7):
            if c_at(t) > k:
                return t
            t = math.floor(h0 + t) + 1 - h0                             # bir sonraki saat başı
        return math.inf

    for r in range(reps):
        # Yolda gelecek hastalar: saatlik dilimlerde Poisson
        arr = []
        t = 0.0
        while t < horizon:
            nxt = min(horizon, math.floor(h0 + t) + 1 - h0)
            lam = lam_h[int(math.floor(h0 + t)) % 24]
            n = rng.poisson(lam * (nxt - t))
            arr.extend(t + rng.random(n) * (nxt - t))
            t = nxt
        arr = np.sort(np.asarray(arr))
        # Başlangıç: muayenedekilerin kalan süresi (üstel varsayım: belleksizlik), kuyruktakiler t=0'da
        free = [-math.inf] * max_c
        busy = rng.exponential(mu_mean, size=in_service) if in_service else []
        for k, b in enumerate(busy[:max_c]):
            free[k] = b
        queue_t = np.zeros(waiting)
        all_arr = np.concatenate([queue_t, arr])
        dur = service_times(rng, len(all_arr), mu_mean, svc_cv)
        j = 0
        for oi, tau in enumerate(offs):
            # τ'dan önce gelen herkesi işle
            while j < len(all_arr) and all_arr[j] <= tau:
                a = all_arr[j]
                best, bk = math.inf, -1
                for k in range(max_c):
                    s = on_shift(k, max(a, free[k]))
                    if s < best:
                        best, bk = s, k
                if bk >= 0 and math.isfinite(best):
                    free[bk] = best + dur[j]
                j += 1
            # τ anında gelen sanal hasta
            best = min(on_shift(k, max(tau, free[k])) for k in range(max_c))
            out[r, oi] = (best - tau) * 60 if math.isfinite(best) else math.nan

    res = []
    for oi, tau in enumerate(offs):
        col = out[:, oi]
        col = col[np.isfinite(col)]
        if len(col) == 0:
            res.append({"dakika": round(tau * 60), "alt": None, "orta": None, "ust": None})
            continue
        lo, mid, hi = (float(np.quantile(col, q)) for q in QUANTILES)
        res.append({"dakika": round(tau * 60), "alt": round(lo, 1), "orta": round(mid, 1), "ust": round(hi, 1)})
    return res
