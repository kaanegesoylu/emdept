"""Yoğunluk analizi, dağılım kontrolü ve saatlik hekim kararı."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd
from scipy import stats

from .queueing import Target, lagged_rates, p_within, queue_stats, required_servers

DayFilter = Literal["all", "weekday", "weekend"]
SvcSource = Literal["auto", "end", "exit", "manual"]


def dispersion_test(counts: np.ndarray) -> tuple[float, float, float, float]:
    """Yayılım indeksi testi. Döner: (ortalama, varyans, D = varyans/ortalama, iki yönlü p).

    Poisson'da D ≈ 1; (n-1)·D ~ χ²(n-1).
    """
    n = len(counts)
    m = float(np.mean(counts)) if n else math.nan
    v = float(np.var(counts, ddof=1)) if n > 1 else math.nan
    if n < 3 or not m > 0:
        return m, v, math.nan, math.nan
    d = v / m
    cdf = stats.chi2.cdf((n - 1) * d, n - 1)
    return m, v, d, float(min(1.0, 2 * min(cdf, 1 - cdf)))


@dataclass
class Analysis:
    n_days: int
    days_used: int
    first_day: pd.Timestamp
    last_day: pd.Timestamp
    total: int
    daily_mean: float
    hourly: pd.DataFrame          # index 0..23: lam, var, D, p, n, c, rho, obs_mean, obs_p90, obs_within, obs_n
    heat: pd.DataFrame            # 7 × 24 ortalama geliş (Pzt..Paz)
    pooled_D: float
    svc_source: str
    svc_mean: float               # dakika
    svc_cv: float
    svc_durations: np.ndarray
    fill: dict
    obs_mean: float
    obs_within: float
    los_mean: float

    @property
    def mu(self) -> float:
        return 60 / self.svc_mean

    @property
    def poisson_ok_hours(self) -> int:
        return int((self.hourly["p"] >= 0.05).sum())


DAY_NAMES = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]


def analyze(patients: pd.DataFrame, staffing: list[int], day_filter: DayFilter = "all",
            svc_source: SvcSource = "auto", manual_min: float = 12, manual_cv: float = 1.0,
            T: float = 30) -> Analysis | None:
    if patients is None or patients.empty:
        return None
    p = patients
    day0 = p["arrival"].min().normalize()
    day_idx = ((p["arrival"] - day0) // pd.Timedelta(days=1)).astype(int)
    hour = p["arrival"].dt.hour
    n_days = int(day_idx.max()) + 1
    counts = np.zeros((n_days, 24))
    np.add.at(counts, (day_idx.to_numpy(), hour.to_numpy()), 1)
    dows = np.array([(day0 + pd.Timedelta(days=d)).dayofweek for d in range(n_days)])
    if day_filter == "weekday":
        sel = dows < 5
    elif day_filter == "weekend":
        sel = dows >= 5
    else:
        sel = np.ones(n_days, bool)
    used = counts[sel]

    rows = [dispersion_test(used[:, h]) for h in range(24)]
    hourly = pd.DataFrame(rows, columns=["lam", "var", "D", "p"])
    hourly["n"] = int(sel.sum())
    hourly["lam"] = hourly["lam"].fillna(0)
    pooled = dispersion_test(used.ravel())[2]

    heat = pd.DataFrame(index=DAY_NAMES, columns=range(24), dtype=float)
    for r in range(7):
        m = dows == r
        heat.iloc[r] = counts[m].mean(axis=0) if m.any() else np.nan

    in_sel = sel[day_idx.to_numpy()]
    ps = p[in_sel]
    fill = {k: int(p[k].notna().sum()) for k in ("start", "end", "exit")}

    src = svc_source
    if src == "auto":
        src = "end" if fill["end"] > 20 else "manual"
    durs = np.array([])
    if src == "end":
        durs = ((ps["end"] - ps["start"]).dt.total_seconds() / 60).dropna().to_numpy()
    elif src == "exit":
        durs = ((ps["exit"] - ps["start"]).dt.total_seconds() / 60).dropna().to_numpy()
    durs = durs[(durs > 0) & (durs < 600)]
    if src != "manual" and len(durs) < 20:
        src, durs = "manual", np.array([])
    if src == "manual":
        svc_mean, svc_cv = manual_min, manual_cv
    else:
        svc_mean = float(durs.mean())
        svc_cv = float(durs.std(ddof=1) / svc_mean)

    mu = 60 / svc_mean
    c = np.asarray(staffing, dtype=float)
    hourly["c"] = c
    with np.errstate(divide="ignore", invalid="ignore"):
        hourly["rho"] = np.where(c > 0, hourly["lam"] / (c * mu), np.where(hourly["lam"] > 0, np.inf, 0))

    w = ((ps["start"] - ps["arrival"]).dt.total_seconds() / 60)
    wh = pd.DataFrame({"h": ps["arrival"].dt.hour, "w": w}).dropna()
    g = wh.groupby("h")["w"]
    hourly["obs_mean"] = g.mean().reindex(range(24))
    hourly["obs_p90"] = g.quantile(0.9).reindex(range(24))
    hourly["obs_within"] = g.apply(lambda s: (s <= T).mean()).reindex(range(24))
    hourly["obs_n"] = g.size().reindex(range(24)).fillna(0).astype(int)

    los = ((ps["exit"] - ps["arrival"]).dt.total_seconds() / 60).dropna()
    los = los[(los >= 0) & (los < 2880)]
    daily_totals = used.sum(axis=1)

    return Analysis(
        n_days=n_days, days_used=int(sel.sum()), first_day=day0, last_day=day0 + pd.Timedelta(days=n_days - 1),
        total=len(p), daily_mean=float(daily_totals.mean()) if len(daily_totals) else math.nan,
        hourly=hourly, heat=heat, pooled_D=pooled, svc_source=src, svc_mean=svc_mean, svc_cv=svc_cv,
        svc_durations=durs, fill=fill,
        obs_mean=float(wh["w"].mean()) if len(wh) else math.nan,
        obs_within=float((wh["w"] <= T).mean()) if len(wh) else math.nan,
        los_mean=float(los.mean()) if len(los) else math.nan,
    )


@dataclass
class Decision:
    table: pd.DataFrame       # saat başına: lam, c, rho, wq_min, within, ok, stable, req, req_wq_min, req_within
    lag_hours: float
    cv2: float

    @property
    def current_total(self) -> int:
        return int(self.table["c"].sum())

    @property
    def required_total(self) -> int:
        return int(self.table["req_filled"].sum())

    @property
    def failing_hours(self) -> int:
        return int((~self.table["ok"]).sum())

    @property
    def unstable_hours(self) -> int:
        return int(((~self.table["stable"]) & (self.table["lam"] > 0)).sum())

    @property
    def capped_hours(self) -> int:
        return int(self.table["req"].isna().sum())

    def recommended_schedule(self) -> list[int]:
        return [int(v) for v in self.table["req_filled"]]


def decide(a: Analysis, target: Target) -> Decision:
    lam = a.hourly["lam"].tolist()
    lag = a.svc_mean / 60 if target.method == "lag" else 0.0
    lam_eff = lagged_rates(lam, lag) if target.method == "lag" else lam
    cv2 = (a.svc_cv ** 2 if math.isfinite(a.svc_cv) else 1.0) if target.model == "mgc" else 1.0
    rows = []
    for h in range(24):
        l, c = lam_eff[h], int(round(a.hourly.at[h, "c"]))
        cur = queue_stats(l, a.mu, c, cv2, target.model)
        req = required_servers(l, a.mu, target, cv2)
        at = queue_stats(l, a.mu, req, cv2, target.model) if req is not None else None
        rows.append({
            "hour": h, "lam": l, "c": c, "rho": cur.rho, "stable": cur.stable,
            "wq_min": cur.wq_min if l > 0 else 0.0, "within": p_within(cur, target.T / 60) if l > 0 else math.nan,
            "ok": l <= 0 or target.met(cur),
            "req": req, "req_filled": req if req is not None else target.max_c,
            "req_wq_min": at.wq_min if at else math.nan,
            "req_within": p_within(at, target.T / 60) if at and l > 0 else math.nan,
        })
    return Decision(pd.DataFrame(rows).set_index("hour"), lag, cv2)
