"""Canlı durum: ESP32 butonlarından ya da simülasyondan anlık kuyruk."""
from __future__ import annotations

import math
from datetime import datetime, timedelta

import plotly.graph_objects as go
import streamlit as st

from acil.live import LiveState, SerialSource, Simulator, list_serial_ports

from .common import C, current, tr

SPEEDS = {1: "1×", 60: "60×", 300: "300×"}
BUTTONS = [("arrival", "Hasta geldi", ":material/person_add:"), ("start", "Muayeneye alındı", ":material/stethoscope:"),
           ("end", "Muayene bitti", ":material/task_alt:"), ("doctor_on", "Hekim girişi", ":material/login:"),
           ("doctor_off", "Hekim çıkışı", ":material/logout:")]


def ensure_state() -> LiveState:
    ss = st.session_state
    if "live" not in ss:
        h = datetime.now().hour
        ss.live = LiveState(doctors=int(ss.staffing[h]))
        ss.live_running = False
        ss.live_speed = 300
        ss.live_mode = "Simülasyon"
        ss.live_serial = None
        ss.live_sim = None
    return ss.live


def start_simulation(lam_h: list[float], mu: float) -> None:
    ss = st.session_state
    ensure_state()
    ss.live_mode = "Simülasyon"
    ss.live_sim = Simulator(lam_h, mu, ss.staffing)
    ss.live_running = True


def advance(live: LiveState, seconds_real: float = 1.0) -> None:
    """Canlı kaynağı ilerletir: simülasyonda hız × gerçek süre, ESP32'de kuyruktaki olayları işler."""
    ss = st.session_state
    if not ss.live_running:
        return
    if ss.live_mode == "Simülasyon" and ss.live_sim:
        ss.live_sim.advance(live, ss.live_speed * seconds_real)
    elif ss.live_serial:
        ss.live_serial.drain(live)
        live.now = datetime.now()
        live._trim()


def render() -> None:
    ss = st.session_state
    st.title("Canlı durum")
    st.caption("Yeşil alandaki butonlardan gelen olaylarla anlık kuyruk. ESP32 bağlı değilken simülasyon çalışır.")
    live = ensure_state()
    a, _ = current()
    lam_h = a.hourly["lam"].tolist() if a else [4.0] * 24
    mu = a.mu if a else 5.0

    c1, c2, c3 = st.columns([2, 2, 1])
    mode = c1.segmented_control("Kaynak", ["Simülasyon", "ESP32 (seri port)"], default=ss.live_mode,
                                label_visibility="collapsed", key="live_mode_sel") or ss.live_mode
    if mode != ss.live_mode:
        ss.live_mode, ss.live_running = mode, False
        if ss.live_serial:
            ss.live_serial.close(); ss.live_serial = None
    if mode == "Simülasyon":
        sp = c2.segmented_control("Hız", list(SPEEDS), default=ss.live_speed, format_func=SPEEDS.get,
                                  label_visibility="collapsed", key="live_speed_sel")
        ss.live_speed = sp or ss.live_speed
        label = "Durdur" if ss.live_running else "Başlat"
        if c3.button(label, type="primary", width="stretch", icon=":material/pause:" if ss.live_running else ":material/play_arrow:"):
            ss.live_running = not ss.live_running
            if ss.live_running:
                ss.live_sim = Simulator(lam_h, mu, ss.staffing)
            st.rerun()
    else:
        ports = list_serial_ports()
        port = c2.selectbox("Port", ports or ["(port bulunamadı)"], label_visibility="collapsed")
        if ss.live_serial is None:
            if c3.button("Bağlan", type="primary", width="stretch", disabled=not ports):
                try:
                    ss.live_serial = SerialSource(port)
                    ss.live_running = True
                    live.now = datetime.now()
                    st.rerun()
                except Exception as e:  # noqa: BLE001
                    st.error(f"Bağlanılamadı: {e}")
        elif c3.button("Kes", width="stretch"):
            ss.live_serial.close(); ss.live_serial = None; ss.live_running = False
            st.rerun()
        if not ports:
            st.caption("ESP32'yi USB ile bağlayın. Port listesi için `pyserial` kurulu olmalı.")

    @st.fragment(run_every=1 if ss.live_running else None)
    def board() -> None:
        advance(live)
        h = live.now.hour
        m = st.columns(4)
        m[0].metric("Bekleyen", len(live.waiting),
                    f"en uzun {tr((live.now - live.waiting[0]).total_seconds() / 60, 0)} dk" if live.waiting else "kuyruk boş", delta_color="off")
        m[1].metric("Muayenede", live.in_service, f"{max(0, live.doctors - live.in_service)} hekim boş", delta_color="off")
        m[2].metric("Aktif hekim", live.doctors, f"çizelgede {ss.staffing[h]}", delta_color="off")
        ew = live.expected_wait_min(mu)
        m[3].metric("Şimdi gelen bekler", "hekim yok" if math.isinf(ew) else f"{tr(ew, 0)} dk",
                    f"{live.now:%H:%M:%S} · son 60 dk {len(live.arrivals)} geliş", delta_color="off")

        hist = [(t, q) for t, q in live.history if t >= live.now - timedelta(hours=3)]
        fig = go.Figure()
        if hist:
            fig.add_scatter(x=[t for t, _ in hist], y=[q for _, q in hist], mode="lines", line=dict(color=C["s1"], width=2.5, shape="hv"),
                            name="Bekleyen", hovertemplate="%{x|%H:%M} · %{y} bekleyen<extra></extra>")
        fig.update_layout(height=240, margin=dict(l=8, r=8, t=8, b=8), showlegend=False)
        fig.update_xaxes(range=[live.now - timedelta(hours=3), live.now], tickformat="%H:%M")
        fig.update_yaxes(rangemode="tozero", title="bekleyen hasta", dtick=1 if max([q for _, q in hist] or [0]) < 8 else None)
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

        b = st.columns(len(BUTTONS))
        for col, (ev, label, icon) in zip(b, BUTTONS):
            if col.button(label, icon=icon, width="stretch", key=f"btn_{ev}"):
                if not live.apply(ev, live.now, "panel"):
                    st.toast("Bu olay şu an uygulanamıyor")
                elif ev == "start" and ss.live_sim:
                    ss.live_sim.busy_until.append(live.now + timedelta(hours=ss.live_sim.rng.exponential(1 / mu)))
                st.rerun(scope="fragment")

        with st.expander("Olay kaydı ve mesaj biçimi"):
            st.code("\n".join(reversed(list(live.log)[-40:])) or "Henüz olay yok.", language="json")
            st.caption('ESP32 her basışta bir satır gönderir: {"device":"esp32-yesil-01","event":"arrival"} · '
                       "event ∈ arrival | start | end | doctor_on | doctor_off · ts yoksa Python alındığı anı yazar.")

    board()
