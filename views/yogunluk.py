"""Yoğunluk sayfası: saatlik geliş hızı, kullanım oranı, dağılım kontrolleri."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from .common import C, HOURS, current, hour_fig, hour_range, rho_color, show, tr

FILTERS = {"all": "Tüm günler", "weekday": "Hafta içi", "weekend": "Hafta sonu"}
SVC = {"auto": "Otomatik", "end": "Muayene bitiş − alınma", "exit": "Çıkış − alınma (üst sınır)", "manual": "Elle gir"}


def render() -> None:
    ss = st.session_state
    st.title("Yoğunluk")
    st.caption("Saat saat kaç hasta geliyor ve hekimler ne kadar meşgul.")

    top = st.columns([3, 1])
    with top[0]:
        f = st.segmented_control("Günler", list(FILTERS), default=ss.day_filter, format_func=FILTERS.get,
                                 label_visibility="collapsed", key="yog_filter")
        if f and f != ss.day_filter:
            ss.day_filter, ss.sim = f, None
            st.rerun()
    with top[1].popover("Muayene süresi", icon=":material/tune:", width="stretch"):
        src = st.selectbox("Kaynak", list(SVC), index=list(SVC).index(ss.svc["source"]), format_func=SVC.get)
        mm = st.number_input("Elle süre (dk)", 1.0, 120.0, float(ss.svc["manual_min"]), 0.5)
        cv = st.number_input("Elle CV", 0.2, 3.0, float(ss.svc["manual_cv"]), 0.05)
        new = {"source": src, "manual_min": mm, "manual_cv": cv}
        if new != ss.svc:
            ss.svc, ss.sim = new, None
            st.rerun()

    a, _ = current()
    if a is None:
        st.info("Önce Veri sayfasından veri üretin ya da yükleyin.")
        return
    hr = a.hourly
    peak = int(hr["lam"].idxmax())
    rho_fin = hr["rho"].replace(np.inf, np.nan)
    worst = int(hr["rho"].idxmax())

    m = st.columns(4)
    m[0].metric("En yoğun saat", hour_range(peak), f"{tr(hr.at[peak, 'lam'], 1)} hasta/saat", delta_color="off")
    m[1].metric("En yüksek kullanım ρ", tr(hr.at[worst, "rho"], 2), hour_range(worst), delta_color="off")
    m[2].metric("Poisson ile uyumlu", f"{a.poisson_ok_hours} / 24 saat")
    m[3].metric("Ort. muayene", f"{tr(a.svc_mean, 1)} dk", f"μ = {tr(a.mu, 2)} hasta/saat", delta_color="off")

    if a.svc_source == "exit":
        st.warning("Muayene süresi çıkış saatinden hesaplanıyor; tetkik beklemesi de dahil olduğu için gereken hekim sayısı olduğundan yüksek çıkar.", icon=":material/warning:")
    elif a.svc_source == "manual":
        st.info(f"Muayene süresi veriden ölçülmüyor; elle girilen {tr(a.svc_mean, 1)} dk kullanılıyor.", icon=":material/info:")

    view = st.segmented_control("Görünüm", ["Geliş hızı", "Kullanım oranı", "Gün × saat"], default="Geliş hızı",
                                label_visibility="collapsed", key="yog_view") or "Geliş hızı"
    if view == "Geliş hızı":
        fig = hour_fig(ytitle="hasta / saat")
        fig.add_bar(x=HOURS, y=hr["lam"], marker_color=C["s1"], name="λ",
                    customdata=np.stack([hr["var"], hr["n"]], axis=1),
                    hovertemplate="%{y:.2f} hasta/saat<br>varyans %{customdata[0]:.2f} · %{customdata[1]} gün<extra></extra>")
        show(fig)
    elif view == "Kullanım oranı":
        y = rho_fin.fillna(1.25)
        ymax = max(1.2, float(np.nanmax(y)) * 1.1)
        fig = hour_fig(ytitle="ρ = λ / (c·μ)", ymax=ymax)
        fig.add_bar(x=HOURS, y=y, marker_color=[rho_color(r) for r in hr["rho"]], name="ρ",
                    customdata=np.stack([hr["c"], hr["lam"]], axis=1),
                    hovertemplate="ρ %{y:.2f}<br>%{customdata[0]:.0f} hekim · λ %{customdata[1]:.2f}<extra></extra>")
        fig.add_hline(y=1, line_dash="dash", line_color=C["crit"], annotation_text="ρ = 1 (kararsız)", annotation_position="top left")
        fig.add_hline(y=0.85, line_dash="dot", line_color=C["muted"], annotation_text="0,85", annotation_position="top left")
        show(fig)
        st.caption("Yeşil < 0,70 · sarı 0,70–0,85 · turuncu 0,85–1 · kırmızı ≥ 1 (kuyruk sınırsız büyür)")
    else:
        z = a.heat.astype(float)
        fig = go.Figure(go.Heatmap(z=z.values, x=HOURS, y=list(z.index), colorscale=[[0, "#cde2fb"], [1, "#0d366b"]],
                                   hovertemplate="%{y} %{x:02d}:00 · %{z:.2f} hasta/saat<extra></extra>",
                                   colorbar=dict(title="hasta/sa", thickness=10), xgap=2, ygap=2))
        fig.update_layout(height=340, margin=dict(l=8, r=8, t=8, b=8))
        fig.update_xaxes(tickvals=HOURS[::3], ticktext=[f"{h:02d}" for h in HOURS[::3]])
        fig.update_yaxes(autorange="reversed")
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    with st.expander("Poisson kontrolü, saat saat"):
        st.write(f"Her saat dilimi için günler arası sayımların varyansı ortalamaya bölünür (D). Poisson'da D ≈ 1; "
                 f"p < 0,05 olan saatte varsayım reddedilir. Tüm saatler tek havuzda incelenseydi D = {tr(a.pooled_D, 2)} "
                 "çıkardı: gün içi değişimin yarattığı yapay aşırı yayılım. Bu yüzden kontrol saat bazında yapılır.")
        def verdict(r):
            if not math.isfinite(r["D"]) or r["n"] < 5:
                return "yetersiz veri"
            if r["p"] >= 0.05:
                return "✓ uyumlu"
            return "▲ aşırı yayılım" if r["D"] > 1 else "▼ düşük yayılım"
        t = pd.DataFrame({"Saat": [hour_range(h) for h in HOURS], "Ortalama": hr["lam"].round(2), "Varyans": hr["var"].round(2),
                          "D": hr["D"].round(2), "p": hr["p"].round(3), "Sonuç": hr.apply(verdict, axis=1)})
        st.dataframe(t, hide_index=True, width="stretch", height=300)

    with st.expander("Muayene süresi dağılımı"):
        if len(a.svc_durations):
            d = a.svc_durations
            hi = float(np.quantile(d, 0.99))
            bins = np.linspace(0, hi, 29)
            cnt, edges = np.histogram(d, bins)
            mid = (edges[:-1] + edges[1:]) / 2
            expc = len(d) * (np.exp(-edges[:-1] / a.svc_mean) - np.exp(-edges[1:] / a.svc_mean))
            fig = go.Figure()
            fig.add_bar(x=mid, y=cnt, name="Gözlenen", marker_color="#6da7ec", width=(edges[1] - edges[0]) * 0.9)
            fig.add_scatter(x=mid, y=expc, name="Üstel (aynı ortalama)", mode="lines", line=dict(color=C["s2"], width=2.5))
            fig.update_layout(height=280, margin=dict(l=8, r=8, t=8, b=8), legend=dict(orientation="h", y=1.08, x=0))
            fig.update_xaxes(title="dakika")
            show(fig)
            ok = 0.8 <= a.svc_cv <= 1.2
            st.write(f"{tr(len(d), 0)} ölçüm · ortalama {tr(a.svc_mean, 1)} dk · medyan {tr(float(np.median(d)), 1)} dk · "
                     f"CV {tr(a.svc_cv, 2)} (üstelde 1). " +
                     ("Üstel varsayımı makul; M/M/c kullanılabilir." if ok else
                      "Üstel varsayımı zayıf; Karar sayfasında M/G/c modelini seçin."))
        else:
            st.write("Muayene süresi veriden ölçülmüyor. Elle girilen değer literatürden ya da yeşil alan sorumlusuyla görüşmeden alınmalı.")
