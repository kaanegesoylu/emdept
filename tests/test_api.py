"""API testleri. Sentetik veriyle çalışır; kişisel veri alanı olmadığını da doğrular."""
from fastapi.testclient import TestClient

import api

client = TestClient(api.app)


def test_durum_reports_source():
    r = client.get("/api/durum").json()
    assert r["veri"]["kind"] in ("synthetic", "real") and "HBYS" in r["canli_akis"]["aciklama"]


def test_canli_prediction_shape():
    r = client.get("/api/tahmin/canli").json()
    assert {"alt_dk", "orta_dk", "ust_dk", "metin", "dayanak", "duzey"} <= r.keys()


def test_gecmis_validates_input():
    assert client.get("/api/tahmin/gecmis", params={"gun": 7, "saat": 3}).status_code == 422
    r = client.get("/api/tahmin/gecmis", params={"gun": 0, "saat": 19}).json()
    assert r["yontem"].startswith("history") and r["ust_dk"] >= r["alt_dk"]


def test_haftalik_has_168_cells():
    assert len(client.get("/api/tahmin/haftalik").json()["hucreler"]) == 168


def test_no_personal_fields():
    for path in ["/api/durum", "/api/tahmin/canli", "/api/tahmin/haftalik"]:
        text = client.get(path).text.lower()
        for word in ("tc", "kimlik", "isim", "telefon_no", "tani"):
            assert f'"{word}"' not in text


def test_hastaneler_has_curves_and_no_location_input():
    r = client.get("/api/hastaneler").json()
    assert len(r["hastaneler"]) >= 2 and r["demo_konum"]["lat"]
    h = r["hastaneler"][0]
    assert h["kurgusal"] is True and len(h["varis_egrisi"]) == 25 and h["varis_egrisi"][0]["dakika"] == 0
