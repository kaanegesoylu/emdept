"""Çekirdek testleri: `pytest` ile çalıştırın. MATLAB çapraz kontrolüyle aynı değerler kullanılır."""
import math

import numpy as np
import pandas as pd
import pytest

from acil.analysis import analyze, decide, dispersion_test
from acil.data_io import build_patients, guess_columns, load_staffing, read_table
from acil.live import LiveState, parse_message
from acil.queueing import Target, erlang_c, lagged_rates, p_within, queue_stats, required_servers
from acil.simulation import validate
from acil.synthetic import DEFAULT_STAFFING, GeneratorParams, generate


# --- kuyruk formülleri ---
def test_erlang_c_known_value():
    assert erlang_c(2, 1.0) == pytest.approx(1 / 3)


def test_erlang_c_single_server_equals_rho():
    # M/M/1'de bekleme olasılığı ρ'dur
    assert erlang_c(1, 0.6) == pytest.approx(0.6)


def test_wq_reference_case():
    # λ=8, μ=5, c=2 → Wq = 21,33 dk (MATLAB betiğiyle aynı vaka)
    st = queue_stats(8, 5, 2)
    assert st.wq_min == pytest.approx(21.333, abs=1e-3)
    assert p_within(st, 0.5) == pytest.approx(0.7380, abs=1e-3)


def test_unstable_when_rho_at_least_one():
    st = queue_stats(10, 5, 2)
    assert not st.stable and math.isinf(st.wq)


def test_required_servers_meets_target():
    t = Target(T=30, P=90)
    c = required_servers(8, 5, t)
    assert t.met(queue_stats(8, 5, c)) and not t.met(queue_stats(8, 5, c - 1))


def test_mgc_reduces_to_mmc_when_cv_is_one():
    assert queue_stats(8, 5, 2, 1.0, "mgc").wq == pytest.approx(queue_stats(8, 5, 2).wq)


def test_lagged_rates_zero_lag_is_identity():
    lam = list(range(24))
    assert lagged_rates(lam, 0) == pytest.approx(lam)


# --- simülasyon formülle tutarlı mı ---
def test_simulation_matches_erlang_c():
    v = validate([8.0] * 24, 12, 1.0, [2] * 24, 30, reps=30, days=14, seed=1)
    sim = np.nansum([x["mean"] * x["n"] for x in v]) / sum(x["n"] for x in v)
    assert sim == pytest.approx(queue_stats(8, 5, 2).wq_min, rel=0.12)


# --- üreteç ve analiz ---
def test_generator_is_reproducible_and_ordered():
    a = generate(GeneratorParams(days=7, seed=3), DEFAULT_STAFFING)
    b = generate(GeneratorParams(days=7, seed=3), DEFAULT_STAFFING)
    pd.testing.assert_frame_equal(a, b)
    assert (a["start"] >= a["arrival"]).all() and (a["end"] >= a["start"]).all()


def test_analysis_recovers_parameters():
    p = GeneratorParams(days=60, daily=120, service_min=12, monday_factor=1, weekend_factor=1, seed=5)
    a = analyze(generate(p, DEFAULT_STAFFING), DEFAULT_STAFFING)
    assert a.daily_mean == pytest.approx(120, rel=0.05)
    assert a.svc_mean == pytest.approx(12, rel=0.05)
    assert a.svc_cv == pytest.approx(1, abs=0.1)
    assert a.poisson_ok_hours >= 19


def test_pooled_dispersion_is_inflated():
    # Saatler tek havuzda incelenince gün içi değişim D'yi büyütür
    a = analyze(generate(GeneratorParams(days=30, seed=2), DEFAULT_STAFFING), DEFAULT_STAFFING)
    assert a.pooled_D > 1.5


def test_dispersion_test_detects_overdispersion():
    rng = np.random.default_rng(0)
    over = rng.negative_binomial(2, 0.2, 200)
    assert dispersion_test(over)[3] < 0.01


def test_decision_recommended_schedule_meets_target():
    a = analyze(generate(GeneratorParams(seed=7), DEFAULT_STAFFING), DEFAULT_STAFFING)
    d = decide(a, Target())
    rec = d.recommended_schedule()
    a2 = analyze(generate(GeneratorParams(seed=7), DEFAULT_STAFFING), rec)
    assert decide(a2, Target()).failing_hours == 0


# --- dosya okuma ---
def test_turkish_csv_with_midnight():
    csv = ("Kayıt Saati;Muayeneye Alınma;Muayene Bitiş;Çıkış\n"
           "05.01.2026 23:50;06.01.2026 00:10;06.01.2026 00:20;06.01.2026 00:40\n").encode()
    raw = read_table(csv, "x.csv")["CSV"]
    m = guess_columns(list(raw.columns))
    assert m["arrival"] == "Kayıt Saati" and m["end"] == "Muayene Bitiş" and m["exit"] == "Çıkış"
    p, rep = build_patients(raw, m)
    assert p.loc[0, "start"] == pd.Timestamp("2026-01-06 00:10")


def test_separate_date_and_time_columns_roll_over_midnight():
    raw = read_table(b"tarih,kayit,muayene_baslangic\n05.01.2026,23:50,00:10\n", "y.csv")["CSV"]
    p, rep = build_patients(raw, guess_columns(list(raw.columns)))
    assert p.loc[0, "start"] == pd.Timestamp("2026-01-06 00:10") and rep.midnight_fixed == 1


def test_iso_dates_and_invalid_rows():
    raw = read_table(b"arrival,exam_start\n2026-01-05 08:00,2026-01-05 07:00\nbozuk,\n", "z.csv")["CSV"]
    p, rep = build_patients(raw, {"arrival": "arrival", "start": "exam_start", "end": None, "exit": None, "date": None})
    assert rep.no_arrival == 1 and rep.start_before_arrival == 1 and pd.isna(p.loc[0, "start"])


def test_staffing_file():
    raw = read_table(b"tarih;saat;hekim_sayisi\n05.01.2026;08:00;2\n06.01.2026;08:00;3\n", "s.csv")["CSV"]
    s = load_staffing(raw)
    assert len(s) == 24 and s[8] in (2, 3)


# --- canlı ---
def test_live_events():
    st = LiveState(doctors=1)
    assert parse_message('{"event":"arrival"}')[0] == "arrival"
    assert parse_message("not json") is None
    t = pd.Timestamp("2026-01-05 18:00").to_pydatetime()
    st.apply("arrival", t)
    st.apply("arrival", t)
    assert st.apply("start", t)
    assert not st.apply("start", t)  # tek hekim meşgul
    assert st.expected_wait_min(5) == pytest.approx(24.0)


# --- hasta ekranı tahmini ---
def test_predict_live_queue_ahead():
    from datetime import datetime
    from acil.predict import predict_live
    st = LiveState(doctors=2)
    t = datetime(2026, 1, 5, 18, 0)
    for _ in range(5):
        st.apply("arrival", t)
    st.apply("start", t); st.apply("start", t)          # 2 hekim meşgul, 3 bekliyor
    p = predict_live(st, mu=5)
    # önünde 3 kişi + kendisi → 4 bitiş, hız 2·5 = 10/saat → ortalama 24 dk
    assert p.method == "live" and p.waiting == 3 and p.low < 24 < p.high
    assert p.mid == pytest.approx(stats_median_gamma(4, 10 / 60), rel=1e-6)


def stats_median_gamma(k, rate):
    from scipy import stats
    return stats.gamma.ppf(0.5, k, scale=1 / rate)


def test_predict_live_free_doctor_is_zero():
    from acil.predict import predict_live
    p = predict_live(LiveState(doctors=2), mu=5)
    assert p.high == 0 and p.range_text() == "5 dk’dan az"


def test_predict_history_uses_same_weekday_and_hour():
    from acil.predict import predict_history
    df = generate(GeneratorParams(days=56, seed=9), DEFAULT_STAFFING)
    when = pd.Timestamp("2026-03-02 19:30")             # pazartesi akşam
    p = predict_history(df, when, DEFAULT_STAFFING, mu=5)
    assert p.method == "history_observed" and "pazartesi" in p.basis and p.n >= 30
    night = predict_history(df, pd.Timestamp("2026-03-03 04:30"), DEFAULT_STAFFING, mu=5)
    assert night.mid < p.mid


def test_predict_history_falls_back_to_model_without_start_times():
    from acil.predict import predict_history
    df = generate(GeneratorParams(days=28, seed=4), DEFAULT_STAFFING).assign(start=pd.NaT)
    staff = [2] * 8 + [3] * 16
    p = predict_history(df, pd.Timestamp("2026-02-02 19:00"), staff, mu=5)
    assert p.method == "history_model" and p.high > p.low >= 0
    q = predict_history(df, pd.Timestamp("2026-02-02 19:00"), DEFAULT_STAFFING, mu=5)
    assert q.method == "unavailable" and q.range_text() == "—"  # 2 hekimle kapasite aşılıyor


def test_database_source_reads_new_rows_only():
    import sqlite3
    from acil.live import DatabaseSource
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE yesil_alan_olaylar (id INTEGER, event TEXT, ts TEXT)")
    conn.executemany("INSERT INTO yesil_alan_olaylar VALUES (?,?,?)",
                     [(1, "arrival", "2026-01-05T18:00:00"), (2, "arrival", "2026-01-05T18:01:00"), (3, "start", "2026-01-05T18:02:00")])
    st, src = LiveState(doctors=1), DatabaseSource(conn)
    assert src.drain(st) == 3 and len(st.waiting) == 1 and st.in_service == 1
    assert src.drain(st) == 0
