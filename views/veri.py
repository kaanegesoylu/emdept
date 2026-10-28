"""Veri sayfası: sentetik üretim, hastane dosyası yükleme, hekim çizelgesi."""
from __future__ import annotations

from dataclasses import replace

import pandas as pd
import streamlit as st

from acil.data_io import FIELDS, build_patients, guess_columns, load_staffing, read_table
from acil.synthetic import PROFILE_LABELS

from .common import current, pct, regenerate, set_staffing, tr

BLOCKS = [("Gece", "00–08", range(0, 8)), ("Gündüz", "08–16", range(8, 16)), ("Akşam", "16–24", range(16, 24))]


@st.cache_data(show_spinner=False)
def _read(data: bytes, name: str) -> dict[str, pd.DataFrame]:
    return read_table(data, name)


def render() -> None:
    ss = st.session_state
    st.title("Veri")
    st.caption("Hastane verisi gelene kadar sistem kendi verisini üretir. Dosya yüklendiğinde tüm sayfalar o veriyle yeniden hesaplanır.")

    kind = st.segmented_control("Kaynak", ["Sentetik üret", "Hastane dosyası"],
                                default="Hastane dosyası" if ss.source == "real" else "Sentetik üret",
                                label_visibility="collapsed", key="veri_kind")

    if kind == "Hastane dosyası":
        _file_box()
    else:
        _synthetic_box()

    st.divider()
    _staffing_box()
    st.divider()
    _summary()


def _synthetic_box() -> None:
    ss = st.session_state
    g = ss.gen
    with st.form("gen_form"):
        c1, c2, c3, c4 = st.columns(4)
        days = c1.number_input("Gün", 3, 400, g.days)
        daily = c2.number_input("Günlük hasta", 5, 1000, int(g.daily))
        svc = c3.number_input("Ort. muayene (dk)", 1.0, 120.0, float(g.service_min), 0.5)
        prof = c4.selectbox("Geliş profili", list(PROFILE_LABELS), index=list(PROFILE_LABELS).index(g.profile),
                            format_func=PROFILE_LABELS.get)
        with st.expander("Gelişmiş ayarlar"):
            a1, a2, a3, a4 = st.columns(4)
            start = a1.date_input("Başlangıç", pd.Timestamp(g.start_date), format="DD.MM.YYYY")
            mon = a2.number_input("Pazartesi katsayısı", 0.5, 2.0, g.monday_factor, 0.05)
            wkd = a3.number_input("Hafta sonu katsayısı", 0.5, 2.0, g.weekend_factor, 0.05)
            cv = a4.number_input("Muayene CV (1 = üstel)", 0.2, 3.0, g.service_cv, 0.05)
            b1, b2, b3, b4 = st.columns(4)
            tp = b1.number_input("Tetkik olasılığı (%)", 0, 100, int(g.test_prob * 100))
            tm = b2.number_input("Ort. tetkik (dk)", 0, 600, int(g.test_min), 5)
            disp = b3.number_input("Günlük dalgalanma (0 = Poisson)", 0.0, 1.0, g.dispersion, 0.05)
            seed = b4.number_input("Tohum", 0, 10**6, g.seed)
        if st.form_submit_button("Veriyi üret", type="primary"):
            ss.gen = replace(g, days=int(days), daily=float(daily), service_min=float(svc), profile=prof,
                             start_date=str(start), monday_factor=mon, weekend_factor=wkd, service_cv=cv,
                             test_prob=tp / 100, test_min=float(tm), dispersion=disp, seed=int(seed))
            regenerate()
            st.toast(f"{len(ss.patients):,} hasta üretildi".replace(",", "."))


def _file_box() -> None:
    ss = st.session_state
    up = st.file_uploader("CSV veya Excel", type=["csv", "txt", "xlsx", "xls"], label_visibility="collapsed")
    st.caption("Her satır bir hasta. Zorunlu: kayıt saati. Önerilen: muayeneye alınma ve muayene bitiş. Veri yalnızca bu bilgisayarda işlenir.")
    if not up:
        with st.expander("Örnek dosya biçimi"):
            st.code("kayit_saati;muayeneye_alinma;muayene_bitis;cikis_saati\n"
                    "05.01.2026 08:14;05.01.2026 08:31;05.01.2026 08:42;05.01.2026 09:05", language=None)
            st.caption("Hazır örnek: `data/ornek_hasta_verisi.csv`")
        return
    try:
        sheets = _read(up.getvalue(), up.name)
    except Exception as e:  # noqa: BLE001
        st.error(f"Dosya açılamadı: {e}")
        return
    name = list(sheets)[0]
    if len(sheets) > 1:
        name = st.selectbox("Sayfa", list(sheets))
    raw = sheets[name].dropna(how="all")
    cols = [str(c) for c in raw.columns]
    raw.columns = cols
    guess = guess_columns(cols)
    opts = ["— yok —"] + cols
    mapping = {}
    mc = st.columns(len(FIELDS))
    for i, (k, label) in enumerate(FIELDS.items()):
        sel = mc[i].selectbox(label, opts, index=opts.index(guess[k]) if guess[k] else 0, key=f"map_{k}")
        mapping[k] = None if sel == "— yok —" else sel
    with st.expander(f"Dosya önizleme · {len(raw):,} satır".replace(",", ".")):
        st.dataframe(raw.head(8), hide_index=True, width="stretch")
    if st.button("Veriyi uygula", type="primary"):
        if not mapping["arrival"]:
            st.error("Kayıt saati sütununu seçin; geliş hızı bu sütundan hesaplanır.")
            return
        patients, rep = build_patients(raw, mapping)
        if len(patients) < 10:
            st.error(f"Yalnızca {len(patients)} geçerli kayıt bulundu. Tarih biçimini kontrol edin "
                     "(05.01.2026 14:23 veya 2026-01-05 14:23). Tarih ve saat ayrıysa “Ayrı tarih sütunu”nu seçin.")
            return
        ss.patients, ss.report = patients, rep
        ss.source, ss.source_name, ss.gen_staffing, ss.sim = "real", up.name, None, None
        st.toast(f"{len(patients):,} kayıt yüklendi".replace(",", "."))
        st.rerun()


def _staffing_box() -> None:
    ss = st.session_state
    st.subheader("Hekim çizelgesi")
    st.caption(f"Yeşil alanda her saatte görevli hekim sayısı · {ss.staff_src}")
    uniform = all(len({ss.staffing[h] for h in r}) == 1 for _, _, r in BLOCKS)
    cols = st.columns(3)
    new = list(ss.staffing)
    for col, (name, span, rng) in zip(cols, BLOCKS):
        vals = [ss.staffing[h] for h in rng]
        v = col.number_input(f"{name} {span}", 0, 40, max(set(vals), key=vals.count), key=f"blk_{name}_{tuple(vals)}")
        if v != max(set(vals), key=vals.count):
            for h in rng:
                new[h] = v
    if new != ss.staffing:
        set_staffing(new, "Elle girildi")
        st.rerun()
    if not uniform:
        st.caption("Çizelge saat saat farklı; kutular her dilimdeki en sık değeri gösteriyor. Bir kutuyu değiştirmek o dilimin tamamını yazar.")
    with st.expander("Saat saat düzenle veya dosyadan yükle"):
        df = pd.DataFrame({"Saat": [f"{h:02d}:00" for h in range(24)], "Hekim": ss.staffing}).set_index("Saat").T
        ed = st.data_editor(df, width="stretch", key=f"staff_ed_{tuple(ss.staffing)}")
        vals = [int(v) for v in ed.iloc[0].tolist()]
        if vals != ss.staffing:
            set_staffing(vals, "Saat saat düzenlendi")
            st.rerun()
        f = st.file_uploader("Çizelge dosyası (saat, hekim_sayisi)", type=["csv", "txt", "xlsx", "xls"], key="staff_up")
        if f and st.button("Çizelgeyi yükle"):
            sheet = list(_read(f.getvalue(), f.name).values())[0]
            sch = load_staffing(sheet)
            if sch:
                set_staffing(sch, f"Dosyadan: {f.name} (saatlik ortalama)")
                st.rerun()
            else:
                st.error("Dosyada ‘saat’ ve ‘hekim_sayisi’ sütunları bulunamadı.")


def _summary() -> None:
    ss = st.session_state
    a, _ = current()
    if a is None:
        st.info("Henüz veri yok.")
        return
    n = a.total
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Kayıt", tr(n, 0))
    c2.metric("Dönem", f"{a.n_days} gün", f"{a.first_day:%d.%m.%Y} – {a.last_day:%d.%m.%Y}", delta_color="off")
    c3.metric("Günlük ort. hasta", tr(a.daily_mean, 1))
    c4.metric("Ort. bekleme (gözlenen)", f"{tr(a.obs_mean, 1)} dk" if a.fill["start"] else "ölçülmüyor")

    warn = []
    if a.fill["end"] == 0:
        warn.append("Muayene bitiş saati yok: hizmet süresi veriden ölçülemiyor, elle girilen değer kullanılır. "
                    "“Çıkış − muayeneye alınma” tetkik beklemesini de içerdiği için yerine kullanılmamalı.")
    if a.fill["start"] == 0:
        warn.append("Muayeneye alınma saati yok: gerçek bekleme ölçülemez, model veriyle doğrulanamaz.")
    if a.n_days < 14:
        warn.append("Dönem kısa: saat bazlı Poisson kontrolü için en az 14 gün, tercihen 3 ay önerilir.")
    for w in warn:
        st.warning(w, icon=":material/warning:")

    with st.expander("Veri kalitesi ve önizleme"):
        q1, q2, q3, q4 = st.columns(4)
        q1.metric("Muayeneye alınma dolu", pct(a.fill["start"] / n))
        q2.metric("Muayene bitiş dolu", pct(a.fill["end"] / n))
        q3.metric("Çıkış dolu", pct(a.fill["exit"] / n))
        q4.metric("Ort. kalış (tetkik dahil)", f"{tr(a.los_mean, 0)} dk")
        if ss.report:
            msgs = ss.report.messages()
            st.write(("Kontrol: " + "; ".join(msgs) + ". Sorunlu alanlar boş sayıldı.") if msgs
                     else "Kontrol: tüm satırlar okundu, tutarsız zaman bulunmadı.")
        p = ss.patients.head(10).copy()
        view = pd.DataFrame({
            "Kayıt": p["arrival"].dt.strftime("%d.%m.%Y %H:%M"),
            "Muayeneye alınma": p["start"].dt.strftime("%H:%M"),
            "Muayene bitiş": p["end"].dt.strftime("%H:%M"),
            "Çıkış": p["exit"].dt.strftime("%H:%M"),
            "Bekleme (dk)": ((p["start"] - p["arrival"]).dt.total_seconds() / 60).round(1),
            "Muayene (dk)": ((p["end"] - p["start"]).dt.total_seconds() / 60).round(1),
        })
        st.dataframe(view, hide_index=True, width="stretch")
