"""Karar sayfası: hedef bekleme süresi için saat başına gereken hekim."""
from __future__ import annotations

import math
from dataclasses import replace

import numpy as np
import pandas as pd
import streamlit as st

from acil.simulation import validate

from .common import C, HOURS, current, hour_fig, hour_range, pct, set_staffing, show, step_trace, tr

MODES = {"pct": "Hastaların %P'si T dakika içinde", "mean": "Ortalama bekleme ≤ T dakika"}
MODELS = {"mmc": "M/M/c (Erlang C)", "mgc": "M/G/c (Allen–Cunneen)"}
METHODS = {"sipp": "SIPP (her saat bağımsız)", "lag": "Lag-SIPP (Green ve ark., 2006)"}


def render() -> None:
    ss = st.session_state
    t = ss.target
    st.title("Karar")
    st.caption("Hedef bekleme süresini sağlamak için saat başına kaç hekim gerekir.")

    c1, c2, c3 = st.columns([1, 1, 2])
    T = c1.number_input("Hedef T (dk)", 1, 600, int(t.T))
    P = c2.number_input("Hastaların yüzdesi P", 50, 99, int(t.P), disabled=t.mode != "pct")
    with c3.popover("Model ayarları", icon=":material/tune:", width="stretch"):
        mode = st.radio("Hedef türü", list(MODES), index=list(MODES).index(t.mode), format_func=MODES.get)
        model = st.radio("Model", list(MODELS), index=list(MODELS).index(t.model), format_func=MODELS.get)
        method = st.radio("Saatlik yöntem", list(METHODS), index=list(METHODS).index(t.method), format_func=METHODS.get)
        max_c = st.number_input("Üst sınır (hekim)", 1, 40, t.max_c)
    new = replace(t, T=float(T), P=float(P), mode=mode, model=model, method=method, max_c=int(max_c))
    if new != t:
        ss.target, ss.sim = new, None
        st.rerun()
    st.caption(f"Hedef: {'en az %' + tr(t.P, 0) + ' hasta ' + tr(t.T, 0) + ' dk içinde muayenede' if t.mode == 'pct' else 'ortalama bekleme ≤ ' + tr(t.T, 0) + ' dk'}. "
               "Hedef değerler hastane ve danışmanla belirlenmeli.")

    a, d = current()
    if a is None:
        st.info("Önce Veri sayfasından veri üretin ya da yükleyin.")
        return
    tb = d.table
    diff = d.required_total - d.current_total
    worst = int(tb["wq_min"].replace(np.inf, 1e9).idxmax())

    m = st.columns(4)
    m[0].metric("Hedef dışı saat", f"{d.failing_hours} / 24", f"{d.unstable_hours} saat kararsız" if d.unstable_hours else None, delta_color="off")
    m[1].metric("Mevcut", f"{d.current_total} hekim·saat")
    m[2].metric("Önerilen", f"{d.required_total} hekim·saat", f"{diff:+d}" if diff else "değişiklik yok", delta_color="inverse")
    m[3].metric("En uzun bekleme (model)", f"{tr(tb.at[worst, 'wq_min'], 0)} dk", hour_range(worst), delta_color="off")

    fig = hour_fig(height=360, ytitle="hekim", ymax=max(3, int(max(tb["req_filled"].max(), tb["c"].max())) + 1))
    fig.add_trace(step_trace(tb["c"].tolist(), "Mevcut", C["s1"]))
    fig.add_trace(step_trace(tb["req_filled"].tolist(), "Önerilen", C["s2"], "dash"))
    fig.add_scatter(x=HOURS, y=tb["c"], mode="markers", marker=dict(size=14, opacity=0), showlegend=False,
                    customdata=np.stack([tb["req_filled"], tb["rho"], tb["wq_min"].replace(np.inf, np.nan)], axis=1),
                    hovertemplate="mevcut %{y} · önerilen %{customdata[0]}<br>ρ %{customdata[1]:.2f} · bekleme %{customdata[2]:.1f} dk<extra></extra>")
    fig.update_yaxes(dtick=1)
    show(fig)
    if d.capped_hours:
        st.warning(f"{d.capped_hours} saatte {t.max_c} hekim bile hedefi sağlamıyor; üst sınırı artırın.", icon=":material/warning:")
    if st.button("Önerilen çizelgeyi uygula", icon=":material/check:", disabled=diff == 0 and not d.failing_hours):
        set_staffing(d.recommended_schedule(), "Karar sayfasından önerilen")
        st.toast("Önerilen çizelge uygulandı")
        st.rerun()

    with st.expander("Bekleme süresi: model ve veri"):
        fig = hour_fig(height=300, ytitle="dakika")
        cur = tb["wq_min"].where(np.isfinite(tb["wq_min"]))
        fig.add_scatter(x=HOURS, y=cur, name="Model · mevcut", mode="lines+markers", line=dict(color=C["s1"], width=2))
        fig.add_scatter(x=HOURS, y=tb["req_wq_min"], name="Model · önerilen", mode="lines+markers", line=dict(color=C["s2"], width=2))
        has_obs = a.fill["start"] > 0
        if has_obs:
            obs = a.hourly["obs_mean"].where(a.hourly["obs_n"] >= 3)
            fig.add_scatter(x=HOURS, y=obs, name="Gözlenen", mode="lines+markers", line=dict(color=C["s3"], width=2))
        if t.mode == "mean":
            fig.add_hline(y=t.T, line_dash="dash", line_color=C["muted"], annotation_text=f"T = {tr(t.T, 0)} dk")
        show(fig)
        if has_obs:
            ok = tb["stable"] & (a.hourly["obs_n"] >= 10)
            mae = float((tb.loc[ok, "wq_min"] - a.hourly.loc[ok, "obs_mean"]).abs().mean()) if ok.any() else math.nan
            changed = ss.gen_staffing is not None and ss.gen_staffing != ss.staffing
            st.write(f"Model ile gözlenen bekleme arasındaki ortalama mutlak fark: **{tr(mae, 1)} dk** ({int(ok.sum())} saat). " +
                     ("Çizelge, verinin üretildiği çizelgeden farklı; gözlenen bekleme eski çizelgeye ait." if changed else
                      "Yoğun saatlerden sonraki birikmeyi SIPP yakalayamaz; farkı simülasyonla inceleyin."))
        else:
            st.write("Veride muayeneye alınma saati olmadığı için model gözlenen bekleme ile karşılaştırılamıyor.")

    with st.expander("Saatlik tablo"):
        def status(r):
            if r["lam"] <= 0:
                return "hasta yok"
            if not r["stable"]:
                return "▲ kararsız"
            return "✓ tutuyor" if r["ok"] else "● hedef dışı"
        view = pd.DataFrame({
            "Saat": [hour_range(h) for h in HOURS], "λ /sa": tb["lam"].round(2), "Mevcut c": tb["c"],
            "ρ": tb["rho"].round(2), "Bekleme dk": tb["wq_min"].round(1),
            f"{tr(t.T, 0)} dk içinde": tb["within"].map(pct), "Durum": tb.apply(status, axis=1),
            "Önerilen c": tb["req"].map(lambda v: f"> {t.max_c}" if pd.isna(v) else int(v)),
            "Önerilenle bekleme": tb["req_wq_min"].round(1), "Önerilenle T içinde": tb["req_within"].map(pct),
        })
        st.dataframe(view, hide_index=True, width="stretch", height=420)
        st.caption(f"{MODELS[t.model]} · {METHODS[t.method]}" + (f", gecikme {tr(d.lag_hours * 60, 0)} dk" if t.method == "lag" else "") + f" · μ = {tr(a.mu, 2)}/sa")

    with st.expander("Simülasyonla doğrula"):
        st.write("Formül her saati kararlı kabul eder. Ayrık olay simülasyonu saatler arası birikmeyi de hesaba katar: "
                 "aynı geliş hızlarıyla 20 tekrar × 14 gün, ilk gelen ilk hizmet alır.")
        if st.button("Simülasyonu çalıştır", type="primary"):
            with st.spinner("Simülasyon çalışıyor…"):
                cv = a.svc_cv if math.isfinite(a.svc_cv) else 1.0
                lam = a.hourly["lam"].tolist()
                ss.sim = {"cur": validate(lam, a.svc_mean, cv, ss.staffing, t.T),
                          "rec": validate(lam, a.svc_mean, cv, d.recommended_schedule(), t.T)}
        if ss.sim:
            s = ss.sim
            fig = hour_fig(height=300, ytitle="ort. bekleme (dk)")
            fig.add_scatter(x=HOURS, y=[x["mean"] for x in s["cur"]], name="Simülasyon · mevcut", mode="lines+markers", line=dict(color=C["s1"], width=2))
            fig.add_scatter(x=HOURS, y=[x["mean"] for x in s["rec"]], name="Simülasyon · önerilen", mode="lines+markers", line=dict(color=C["s2"], width=2))
            fig.add_hline(y=t.T, line_dash="dash", line_color=C["muted"], annotation_text=f"T = {tr(t.T, 0)} dk")
            show(fig)

            def agg(rows):
                n = sum(r["n"] for r in rows)
                return (sum(r["mean"] * r["n"] for r in rows if r["n"]) / n, sum(r["within"] * r["n"] for r in rows if r["n"]) / n)
            (mc, wc), (mr, wr) = agg(s["cur"]), agg(s["rec"])
            k = st.columns(2)
            k[0].metric("Mevcut çizelge", f"{tr(mc, 1)} dk ort.", f"{pct(wc)} hasta {tr(t.T, 0)} dk içinde", delta_color="off")
            k[1].metric("Önerilen çizelge", f"{tr(mr, 1)} dk ort.", f"{pct(wr)} hasta {tr(t.T, 0)} dk içinde", delta_color="off")
