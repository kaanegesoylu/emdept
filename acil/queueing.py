"""Kuyruk formülleri: M/M/c (Erlang C), M/G/c (Allen–Cunneen) ve saatlik personel kararı.

Birimler: λ ve μ saatlik (hasta/saat), süreler saat cinsinden döner.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal, Sequence

Model = Literal["mmc", "mgc"]
Mode = Literal["pct", "mean"]


def erlang_c(c: int, a: float) -> float:
    """Gelen hastanın beklemek zorunda kalma olasılığı C(c, a).

    c: hekim sayısı, a = λ/μ sunulan yük. a ≥ c ise sistem kararsızdır, 1 döner.
    Erlang B özyinelemesiyle hesaplanır (büyük c'de taşma olmaz).
    """
    if c <= 0 or a >= c:
        return 1.0
    b = 1.0
    for k in range(1, c + 1):
        b = a * b / (k + a * b)
    return c * b / (c - a * (1 - b))


@dataclass(frozen=True)
class QueueStats:
    lam: float
    mu: float
    c: int
    rho: float
    stable: bool
    p_wait: float          # C(c, a)
    wq: float              # ortalama bekleme (saat)
    rate: float            # bekleme kuyruğunun üstel azalma hızı (saat⁻¹)

    @property
    def wq_min(self) -> float:
        return self.wq * 60


def queue_stats(lam: float, mu: float, c: int, cv2: float = 1.0, model: Model = "mmc") -> QueueStats:
    """Bir saat dilimi için kararlı durum bekleme istatistikleri."""
    a = lam / mu
    rho = a / c if c > 0 else math.inf
    if lam <= 0:
        return QueueStats(lam, mu, c, 0.0, True, 0.0, 0.0, math.inf)
    if c <= 0 or a >= c:
        return QueueStats(lam, mu, c, rho, False, 1.0, math.inf, 0.0)
    p = erlang_c(c, a)
    f = (1 + cv2) / 2 if model == "mgc" else 1.0
    rate = (c * mu - lam) / f
    return QueueStats(lam, mu, c, rho, True, p, p / rate, rate)


def p_within(st: QueueStats, t_hours: float) -> float:
    """P(bekleme ≤ t). M/G/c için yaklaşık."""
    if not st.stable:
        return 0.0
    if st.p_wait == 0:
        return 1.0
    return 1 - st.p_wait * math.exp(-st.rate * t_hours)


@dataclass(frozen=True)
class Target:
    """Karar hedefi. mode='pct': hastaların en az %P'si T dk içinde; mode='mean': ortalama ≤ T dk."""
    T: float = 30
    P: float = 90
    mode: Mode = "pct"
    model: Model = "mmc"
    method: Literal["sipp", "lag"] = "sipp"
    max_c: int = 12

    def met(self, st: QueueStats) -> bool:
        if not st.stable:
            return False
        if self.mode == "mean":
            return st.wq <= self.T / 60
        return p_within(st, self.T / 60) >= self.P / 100


def required_servers(lam: float, mu: float, target: Target, cv2: float = 1.0) -> int | None:
    """Hedefi sağlayan en küçük hekim sayısı; üst sınırda bile sağlanmıyorsa None."""
    if lam <= 0:
        return 0
    for c in range(max(1, math.floor(lam / mu) + 1), target.max_c + 1):
        if target.met(queue_stats(lam, mu, c, cv2, target.model)):
            return c
    return None


def lagged_rates(lam: Sequence[float], lag_hours: float) -> list[float]:
    """Lag-SIPP (Green ve ark., 2006): geliş eğrisini lag kadar geciktir (dairesel, doğrusal ara değer)."""
    n = len(lam)
    out = []
    for h in range(n):
        t = h - lag_hours
        i0 = math.floor(t)
        fr = t - i0
        out.append(lam[i0 % n] * (1 - fr) + lam[(i0 + 1) % n] * fr)
    return out
