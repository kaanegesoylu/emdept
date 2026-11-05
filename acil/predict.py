"""Hastaya gösterilecek tahmini bekleme süresi.

İki yol vardır:

1. Canlı tahmin (predict_live): hastanenin veritabanına (HBYS) anlık erişim olduğu varsayımı.
   Şu an kuyrukta kaç kişi olduğu ve kaç hekimin görevde olduğu bilinir; muayene hızı μ geçmişten öğrenilir.
   Şimdi gelen hastanın beklemesi, önündeki m hastanın muayeneye alınması için gereken süredir.
   Tüm hekimler meşgulken muayene bitişleri c·μ hızında gelir, bu yüzden bekleme ≈ Gamma(m, c·μ).

2. Geçmişe dayalı tahmin (predict_history): anlık bilgi yok, yalnızca geçmiş kayıtlar var.
   Aynı gün ve saatte geçmişte gözlenen beklemelerin dağılımı kullanılır. Muayeneye alınma saati
   kayıtlı değilse geçmişten öğrenilen λ ve μ ile Erlang C dağılımına düşülür.

Her iki yol da tek bir sayı değil, bir aralık verir (varsayılan: hastaların yarısının düştüğü %25–%75).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats

from .live import LiveState
from .queueing import queue_stats

QUANTILES = (0.25, 0.50, 0.75)
MIN_SAMPLES = 30
DAY_NAMES = ["pazartesi", "salı", "çarşamba", "perşembe", "cuma", "cumartesi", "pazar"]


@dataclass
class Prediction:
    low: float                 # dakika
    mid: float
    high: float
    method: str                # "live" | "history_observed" | "history_model" | "no_doctor" | "unavailable"
    basis: str                 # hastaya/görevliye kısa açıklama
    waiting: int | None = None # canlı modda bekleyen hasta
    doctors: int | None = None
    level: str = "sakin"       # sakin | yogun | cok_yogun
    n: int = 0                 # dayanak gözlem sayısı
    extra: dict = field(default_factory=dict)

    def range_text(self, step: int = 5) -> str:
        """Hastaya gösterilecek aralık: 5 dakikaya yuvarlanır, alt sınır en az 0."""
        if self.method in ("no_doctor", "unavailable") or not math.isfinite(self.high):
            return "—"
        lo = int(step * math.floor(self.low / step))
        hi = int(step * math.ceil(self.high / step))
        if hi <= step:
            return f"{step} dk’dan az"
        if lo == hi:
            hi = lo + step
        return f"{lo}–{hi} dk"


def _level(mid_min: float) -> str:
    if mid_min < 15:
        return "sakin"
    if mid_min < 40:
        return "yogun"
    return "cok_yogun"


# ---------- 1. canlı ----------
def predict_live(state: LiveState, mu: float, svc_cv: float = 1.0, q=QUANTILES) -> Prediction:
    """Anlık kuyruk durumundan tahmin (HBYS erişimi varsayımı)."""
    c = state.doctors
    waiting = len(state.waiting)
    if c <= 0:
        return Prediction(math.nan, math.nan, math.nan, "no_doctor", "Şu an görevde hekim görünmüyor.",
                          waiting, c, "cok_yogun")
    free = c - state.in_service
    m = waiting + 1 - max(0, free)          # bu hastanın muayeneye girmesi için gereken bitiş sayısı
    if m <= 0:
        return Prediction(0, 0, 0, "live", "Boş hekim var.", waiting, c, "sakin")
    rate = c * mu / 60                       # dakikada bitiş
    # Muayene süresi üstel değilse varyansı CV² ile ölçekle (yaklaşık)
    cv2 = svc_cv ** 2 if math.isfinite(svc_cv) else 1.0
    shape, scale = m / cv2, cv2 / rate
    lo, mid, hi = (float(stats.gamma.ppf(x, shape, scale=scale)) for x in q)
    return Prediction(lo, mid, hi, "live", f"Önünüzde {waiting} hasta, {c} hekim görevde.",
                      waiting, c, _level(mid), extra={"m": m, "rate_per_min": rate})


# ---------- 2. geçmiş ----------
def _select(patients: pd.DataFrame, when: pd.Timestamp, weeks: int | None) -> tuple[pd.DataFrame, str]:
    """Aynı saat için en dar yeterli kümeyi seçer: aynı gün → hafta içi/sonu → tüm günler."""
    p = patients
    if weeks:
        p = p[p["arrival"] >= p["arrival"].max() - pd.Timedelta(weeks=weeks)]
    same_hour = p[p["arrival"].dt.hour == when.hour]
    dow = same_hour["arrival"].dt.dayofweek
    tries = [
        (same_hour[dow == when.dayofweek], f"geçmiş {DAY_NAMES[when.dayofweek]} günleri, {when.hour:02d}:00–{(when.hour + 1) % 24:02d}:00"),
        (same_hour[(dow >= 5) == (when.dayofweek >= 5)], f"geçmiş {'hafta sonu' if when.dayofweek >= 5 else 'hafta içi'} günleri, {when.hour:02d}:00–{(when.hour + 1) % 24:02d}:00"),
        (same_hour, f"geçmişte tüm günler, {when.hour:02d}:00–{(when.hour + 1) % 24:02d}:00"),
    ]
    for sel, label in tries:             # gözlenen bekleme için yeterli muayene saati olan ilk küme
        if sel["start"].notna().sum() >= MIN_SAMPLES:
            return sel, label
    for sel, label in tries:             # yoksa λ tahmini için yeterli geliş olan ilk küme
        if len(sel) >= MIN_SAMPLES:
            return sel, label
    return tries[-1]


def _erlang_quantile(p_wait: float, rate_per_min: float, q: float) -> float:
    """P(W ≤ t) = 1 − C·e^(−rate·t) dağılımının q yüzdeliği."""
    if q <= 1 - p_wait:
        return 0.0
    return math.log(p_wait / (1 - q)) / rate_per_min


def predict_history(patients: pd.DataFrame, when: pd.Timestamp, staffing: list[int], mu: float,
                    weeks: int | None = 12, q=QUANTILES) -> Prediction:
    """Yalnızca geçmiş kayıtlarla tahmin. `when`: tahmin yapılan an (gün ve saat önemlidir)."""
    sel, label = _select(patients, when, weeks)
    waits = ((sel["start"] - sel["arrival"]).dt.total_seconds() / 60).dropna()
    waits = waits[(waits >= 0) & (waits < 24 * 60)]
    if len(waits) >= MIN_SAMPLES:
        lo, mid, hi = (float(np.quantile(waits, x)) for x in q)
        return Prediction(lo, mid, hi, "history_observed", f"Dayanak: {label} ({len(waits)} hasta).",
                          level=_level(mid), n=len(waits))
    # Muayeneye alınma saati yoksa: geçmişten λ, μ → Erlang C
    days = sel["arrival"].dt.normalize().nunique()
    if days == 0:
        return Prediction(math.nan, math.nan, math.nan, "unavailable", "Bu saat için geçmiş kayıt yok.")
    lam = len(sel) / days
    c = int(staffing[when.hour])
    st = queue_stats(lam, mu, c)
    if not st.stable:
        return Prediction(math.nan, math.nan, math.nan, "unavailable",
                          f"Bu saatte geçmiş geliş hızı ({lam:.1f}/sa) {c} hekimin kapasitesini aşıyor; bekleme sınırsız büyür.",
                          doctors=c, level="cok_yogun", extra={"lam": lam, "rho": st.rho})
    rate = st.rate / 60
    lo, mid, hi = (_erlang_quantile(st.p_wait, rate, x) for x in q)
    return Prediction(lo, mid, hi, "history_model",
                      f"Dayanak: {label}, ortalama {lam:.1f} hasta/saat, {c} hekim (Erlang C).",
                      doctors=c, level=_level(mid), n=len(sel), extra={"lam": lam, "rho": st.rho})


def history_grid(patients: pd.DataFrame, staffing: list[int], mu: float, weeks: int | None = 12) -> pd.DataFrame:
    """Gün × saat (7 × 24) tahmin tablosu: her hücre için (alt, orta, üst) dakika ve yöntem.

    Döner: uzun biçimli DataFrame — dow, hour, low, mid, high, method, n.
    """
    p = patients
    if weeks:
        p = p[p["arrival"] >= p["arrival"].max() - pd.Timedelta(weeks=weeks)]
    w = ((p["start"] - p["arrival"]).dt.total_seconds() / 60)
    df = pd.DataFrame({"dow": p["arrival"].dt.dayofweek, "hour": p["arrival"].dt.hour, "w": w}).dropna()
    df = df[(df["w"] >= 0) & (df["w"] < 24 * 60)]
    g = df.groupby(["dow", "hour"])["w"]
    obs = g.quantile(list(QUANTILES)).unstack()
    cnt = g.size()
    rows = []
    base = pd.Timestamp("2026-01-05")  # pazartesi; yalnız gün ve saat kullanılır
    for d in range(7):
        for h in range(24):
            if (d, h) in cnt.index and cnt[(d, h)] >= MIN_SAMPLES:
                lo, mid, hi = obs.loc[(d, h)].tolist()
                rows.append((d, h, lo, mid, hi, "history_observed", int(cnt[(d, h)])))
            else:
                pr = predict_history(patients, base + pd.Timedelta(days=d, hours=h), staffing, mu, weeks)
                rows.append((d, h, pr.low, pr.mid, pr.high, pr.method, pr.n))
    return pd.DataFrame(rows, columns=["dow", "hour", "low", "mid", "high", "method", "n"])
