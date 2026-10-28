"""Sayfaların ortak durumu, hesaplama ve grafik yardımcıları."""
from __future__ import annotations

import math
from dataclasses import asdict

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from acil.analysis import Analysis, Decision, analyze, decide
from acil.queueing import Target
from acil.synthetic import DEFAULT_STAFFING, GeneratorParams, generate

# Grafik renkleri (renk körlüğüne göre doğrulanmış sıra)
C = {
    "s1": "#2a78d6", "s2": "#eb6834", "s3": "#1baf7a",
    "good": "#0ca30c", "warn": "#fab219", "serious": "#ec835a", "crit": "#d03b3b",
    "muted": "#898781",
}
HOURS = list(range(24))
HOUR_LABELS = [f"{h:02d}:00" for h in HOURS]


def hour_range(h: int) -> str:
    return f"{h:02d}–{(h + 1) % 24:02d}"


def tr(x: float, d: int = 1) -> str:
    """Türkçe sayı biçimi (ondalık virgül)."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "–"
    if isinstance(x, float) and math.isinf(x):
        return "∞"
    s = f"{x:,.{d}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def pct(x: float, d: int = 0) -> str:
    return "–" if x is None or (isinstance(x, float) and math.isnan(x)) else "%" + tr(x * 100, d)


# ---------- durum ----------
def init_state() -> None:
    ss = st.session_state
    if "staffing" not in ss:
        ss.staffing = list(DEFAULT_STAFFING)
        ss.staff_src = "Varsayılan (gece 1, gündüz 2)"
        ss.gen = GeneratorParams()
        ss.target = Target()
        ss.day_filter = "all"
        ss.svc = {"source": "auto", "manual_min": 12.0, "manual_cv": 1.0}
        ss.sim = None
        regenerate()


def regenerate() -> None:
    ss = st.session_state
    ss.patients = generate(ss.gen, ss.staffing)
    ss.gen_staffing = list(ss.staffing)
    ss.source = "synthetic"
    ss.source_name = "Sentetik veri"
    ss.report = None
    ss.sim = None


def set_staffing(values: list[int], source: str) -> None:
    st.session_state.staffing = [int(max(0, v)) for v in values]
    st.session_state.staff_src = source
    st.session_state.sim = None


def current() -> tuple[Analysis | None, Decision | None]:
    ss = st.session_state
    a = analyze(ss.patients, ss.staffing, ss.day_filter, ss.svc["source"],
                ss.svc["manual_min"], ss.svc["manual_cv"], ss.target.T)
    d = decide(a, ss.target) if a else None
    return a, d


def source_badge() -> None:
    ss = st.session_state
    if ss.source == "real":
        st.sidebar.success(f"Gerçek veri\n\n{ss.source_name}", icon=":material/verified:")
    else:
        st.sidebar.info("Sentetik veri\n\nÖrnek varsayımlar, hastane verisi değil.", icon=":material/science:")


# ---------- grafik ----------
def hour_fig(height: int = 380, ytitle: str | None = None, ymax: float | None = None) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        height=height, margin=dict(l=8, r=8, t=8, b=8), hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        bargap=0.3,
    )
    fig.update_xaxes(tickvals=HOURS[::3], ticktext=[f"{h:02d}" for h in HOURS[::3]],
                     range=[-0.6, 23.6], showgrid=False, title=None)
    fig.update_yaxes(title=ytitle, rangemode="tozero", zeroline=False, gridwidth=1)
    if ymax:
        fig.update_yaxes(range=[0, ymax])
    return fig


def step_trace(values: list[float], name: str, color: str, dash: str | None = None) -> go.Scatter:
    xs, ys = [], []
    for h, v in enumerate(values):
        xs += [h - 0.5, h + 0.5]
        ys += [v, v]
    return go.Scatter(x=xs, y=ys, name=name, mode="lines", line=dict(color=color, width=2.5, dash=dash),
                      hoverinfo="skip")


def show(fig: go.Figure) -> None:
    st.plotly_chart(fig, width="stretch", theme="streamlit", config={"displayModeBar": False})


def rho_color(r: float) -> str:
    if not math.isfinite(r) or r >= 1:
        return C["crit"]
    if r >= 0.85:
        return C["serious"]
    if r >= 0.70:
        return C["warn"]
    return C["good"]
