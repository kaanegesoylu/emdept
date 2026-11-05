"""Varış anı tahmini ve hastane öneri kuralı."""
from datetime import datetime

import pytest

from acil.forecast import forecast_curve
from acil.routing import Option, haversine_km, interp, recommend, travel_minutes


def test_queue_effect_fades_with_travel_time():
    # Şu an 10 kişilik kuyruk: hemen varan çok bekler, 3 saat sonra varan daha az
    c = forecast_curve(datetime(2026, 1, 5, 10), waiting=10, in_service=2, doctors_now=2,
                       lam_h=[6] * 24, staffing=[2] * 24, svc_mean_min=12, reps=300, seed=1)
    assert c[0]["orta"] > 40 and c[12]["orta"] < c[0]["orta"] / 2


def test_uncertainty_grows_from_known_state():
    c = forecast_curve(datetime(2026, 1, 5, 10), waiting=0, in_service=0, doctors_now=2,
                       lam_h=[8] * 24, staffing=[2] * 24, svc_mean_min=12, reps=300, seed=2)
    assert c[0]["ust"] == 0 and c[8]["ust"] > 0


def test_staffing_change_on_the_way_is_used():
    # Gece 1 hekim, 08'den sonra 3 hekim: 07:30'da yola çıkan, 08 sonrası varınca daha az bekler
    staff = [1] * 8 + [3] * 16
    c = forecast_curve(datetime(2026, 1, 5, 7, 30), waiting=6, in_service=1, doctors_now=1,
                       lam_h=[4] * 24, staffing=staff, svc_mean_min=12, reps=300, seed=3)
    assert c[4]["orta"] < c[0]["orta"]  # 60 dk sonra


def test_travel_estimates():
    assert haversine_km(38.0, 27.0, 38.0, 27.0) == 0
    assert travel_minutes(5, "araba") == pytest.approx(5 * 1.3 / 30 * 60)
    assert travel_minutes(10, "yuruyus") is None  # 12,5 km yürüyüş önerilmez


def test_interp_midpoint():
    curve = [{"dakika": 0, "alt": 0, "orta": 10, "ust": 20}, {"dakika": 30, "alt": 10, "orta": 30, "ust": 50}]
    assert interp(curve, 15) == pytest.approx((5, 20, 35))


def test_recommend_requires_meaningful_saving():
    near = Option("A", travel=5, wait_lo=40, wait_mid=50, wait_hi=60)
    small = Option("B", travel=15, wait_lo=25, wait_mid=32, wait_hi=40)   # 8 dk kazanç: yetmez
    assert recommend([near, small])[0] == "A"
    big = Option("C", travel=20, wait_lo=0, wait_mid=5, wait_hi=10)       # 30 dk kazanç, belirsizlikten büyük
    assert recommend([near, small, big])[0] == "C"


def test_recommend_rejects_long_trips():
    near = Option("A", travel=5, wait_lo=80, wait_mid=100, wait_hi=120)
    far = Option("D", travel=100, wait_lo=0, wait_mid=0, wait_hi=0)
    assert recommend([near, far])[0] == "A"


def test_recommend_rejects_saving_within_uncertainty():
    near = Option("A", travel=5, wait_lo=10, wait_mid=60, wait_hi=110)    # çok belirsiz
    other = Option("B", travel=10, wait_lo=20, wait_mid=35, wait_hi=50)
    assert recommend([near, other])[0] == "A"
