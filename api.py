"""Hasta uygulaması için tahmin API'si.

Çalıştırma:  uvicorn api:app --host 0.0.0.0 --port 8000 --no-access-log
(Telefon ve bilgisayar aynı Wi-Fi ağında olmalı.)

Etik ve gizlilik ilkeleri
- Uygulama hiçbir kişisel veri göndermez. API kimlik, konum veya cihaz bilgisi istemez ve saklamaz.
  Hastane karşılaştırmasında konum telefonda kalır: telefon her hastanenin "varış eğrisini" indirir,
  yol süresini ve öneriyi kendisi hesaplar.
- Erişim kaydı tutulmaz (--no-access-log).
- Her yanıtta verinin kaynağı (sentetik / gerçek, kurgusal hastane) ve tahminin dayanağı yazılır.

Veri
- Canlı durum: hastane veritabanına (HBYS) anlık erişim varsayımı. Bugün bu akışı her hastane için
  simülasyon üretir (acil/live.py: Simulator). Gerçek erişim olursa DatabaseSource aynı yere takılır.
- Geçmiş: ana hastane için data/gercek/ içinde hasta dosyası varsa o, yoksa sentetik veri.
"""
from __future__ import annotations

import json
import math
import os
import threading
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from acil.analysis import analyze
from acil.data_io import build_patients, guess_columns, load_staffing, read_table
from acil.forecast import forecast_curve
from acil.live import LiveState, Simulator
from acil.predict import Prediction, history_grid, predict_history, predict_live
from acil.synthetic import DEFAULT_STAFFING, GeneratorParams, generate

ROOT = Path(__file__).parent
REAL_DIR = ROOT / "data" / "gercek"
HOSPITAL_FILE = ROOT / "config" / "hastane.json"
HOSPITALS_FILE = ROOT / "config" / "hastaneler.json"
SIM_SPEED = float(os.environ.get("SIM_SPEED", "1"))     # canlı simülasyon hızı (1 = gerçek zaman)
HISTORY_WEEKS = int(os.environ.get("HISTORY_WEEKS", "12"))
CURVE_TTL_S = 30                                        # varış eğrileri bu süre önbellekte kalır
OFFSETS = tuple(range(0, 361, 15))                      # 0–6 saat, 15 dk adımla


def _load_real(staffing: list[int]) -> tuple[pd.DataFrame, list[int], dict] | None:
    if not REAL_DIR.exists():
        return None
    sched = sorted(REAL_DIR.glob("*cizelge*.*"))
    if sched:
        sheet = list(read_table(sched[0].read_bytes(), sched[0].name).values())[0]
        staffing = load_staffing(sheet) or staffing
    for f in sorted(REAL_DIR.glob("*")):
        if f.suffix.lower() not in (".csv", ".xlsx", ".xls") or f in sched:
            continue
        raw = list(read_table(f.read_bytes(), f.name).values())[0]
        raw.columns = [str(c) for c in raw.columns]
        patients, _ = build_patients(raw, guess_columns(list(raw.columns)))
        if len(patients) >= 100:
            return patients, staffing, {"kind": "real", "label": "Hastane verisi", "file": f.name}
    return None


class Hospital:
    """Bir hastanenin geçmişi, analizi ve canlı (simüle) kuyruğu."""

    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        self.id = cfg["id"]
        self.lock = threading.Lock()
        staffing = list(cfg.get("cizelge", DEFAULT_STAFFING))
        real = _load_real(staffing) if cfg.get("ana") else None
        if real:
            self.patients, self.staffing, self.source = real
        else:
            gp = GeneratorParams(days=84, daily=cfg.get("gunluk", 110), profile=cfg.get("profil", "aksam"),
                                 service_min=cfg.get("muayene_dk", 12), seed=cfg.get("tohum", 497))
            self.patients, self.staffing = generate(gp, staffing), staffing
            self.source = {"kind": "synthetic", "label": "Sentetik örnek veri (hastane verisi değildir)"}
        self.a = analyze(self.patients, self.staffing)
        self.mu = self.a.mu
        self.cv = self.a.svc_cv if math.isfinite(self.a.svc_cv) else 1.0
        self.lam = self.a.hourly["lam"].tolist()
        self.live = LiveState(doctors=int(self.staffing[datetime.now().hour]))
        self.sim = Simulator(self.lam, self.mu, self.staffing, seed=cfg.get("tohum", 0) + 1)
        self._grid = None
        self._curve: tuple[float, list[dict]] | None = None
        # Isınma: simülasyonu 3 saat geriden başlatıp bugüne getir, kuyruk boş başlamasın
        self.live.now = datetime.now() - pd.Timedelta(hours=3)
        self.sim.advance(self.live, 3 * 3600)

    @property
    def grid(self) -> pd.DataFrame:
        if self._grid is None:
            self._grid = history_grid(self.patients, self.staffing, self.mu, HISTORY_WEEKS)
        return self._grid

    def step(self, seconds: float) -> None:
        with self.lock:
            self.sim.advance(self.live, seconds)

    def curve(self) -> list[dict]:
        now = time.monotonic()
        if self._curve and now - self._curve[0] < CURVE_TTL_S:
            return self._curve[1]
        with self.lock:
            st = self.live
            c = forecast_curve(st.now, len(st.waiting), st.in_service, st.doctors, self.lam, self.staffing,
                               self.a.svc_mean, self.cv, OFFSETS, reps=300, seed=int(now))
        self._curve = (now, c)
        return c


class Registry:
    def __init__(self) -> None:
        cfg = json.loads(HOSPITALS_FILE.read_text(encoding="utf-8"))
        self.demo_location = cfg.get("demo_konum")
        self.hospitals = {h["id"]: Hospital(h) for h in cfg["hastaneler"]}
        self.main = next((h for h in self.hospitals.values() if h.cfg.get("ana")), next(iter(self.hospitals.values())))
        self._last = time.monotonic()
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        while True:
            time.sleep(1)
            now = time.monotonic()
            dt, self._last = (now - self._last) * SIM_SPEED, now
            for h in self.hospitals.values():
                h.step(dt)


REG: Registry | None = None


def reg() -> Registry:
    global REG
    if REG is None:
        REG = Registry()
    return REG


def _num(x: float | None) -> float | None:
    return None if x is None or not math.isfinite(x) else round(float(x), 1)


def _pred(p: Prediction) -> dict:
    return {"alt_dk": _num(p.low), "orta_dk": _num(p.mid), "ust_dk": _num(p.high), "metin": p.range_text(),
            "yontem": p.method, "dayanak": p.basis, "duzey": p.level, "bekleyen": p.waiting, "hekim": p.doctors,
            "gozlem": p.n}


# ---------- uygulama ----------
app = FastAPI(title="Yeşil Alan Bekleme Tahmini", version="0.2.0",
              description="FENG 497 — hasta uygulaması için tahmin API'si. Kişisel veri işlemez; konum istemez.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])


@app.get("/api/durum")
def durum() -> dict:
    m = reg().main
    return {"veri": m.source, "canli_akis": {"tur": "simulasyon", "aciklama": "Hastane veritabanına (HBYS) anlık erişim varsayımıyla simülasyon",
                                           "hiz": SIM_SPEED},
            "aralik": "Hastaların yarısı bu aralıkta muayeneye alınır (%25–%75)",
            "gecmis_hafta": HISTORY_WEEKS, "zaman": datetime.now().isoformat(timespec="seconds")}


@app.get("/api/tahmin/canli")
def canli() -> dict:
    m = reg().main
    with m.lock:
        p = predict_live(m.live, m.mu, m.cv)
        clock = m.live.now
    return {**_pred(p), "saat": clock.isoformat(timespec="seconds"), "kaynak": "canli_simulasyon"}


@app.get("/api/tahmin/gecmis")
def gecmis(gun: int = Query(..., ge=0, le=6, description="0 = pazartesi"),
           saat: int = Query(..., ge=0, le=23)) -> dict:
    m = reg().main
    when = pd.Timestamp("2026-01-05") + pd.Timedelta(days=gun, hours=saat)  # yalnız gün ve saat kullanılır
    p = predict_history(m.patients, when, m.staffing, m.mu, HISTORY_WEEKS)
    return {**_pred(p), "gun": gun, "saat": saat, "veri": m.source["kind"]}


@app.get("/api/tahmin/haftalik")
def haftalik() -> dict:
    m = reg().main
    cells = [{"gun": int(r.dow), "saat": int(r.hour), "alt_dk": _num(r.low), "orta_dk": _num(r.mid),
              "ust_dk": _num(r.high), "yontem": r.method} for r in m.grid.itertuples()]
    return {"hucreler": cells, "veri": m.source["kind"]}


@app.get("/api/hastaneler")
def hastaneler() -> dict:
    """Karşılaştırma için tüm hastaneler ve varış eğrileri. Konum istenmez; hesap telefonda yapılır."""
    r = reg()
    out = []
    for h in r.hospitals.values():
        with h.lock:
            p = predict_live(h.live, h.mu, h.cv)
            clock = h.live.now
        out.append({
            "id": h.id, "ad": h.cfg["ad"], "kurgusal": h.cfg.get("kurgusal", False), "ana": h.cfg.get("ana", False),
            "lat": h.cfg["lat"], "lon": h.cfg["lon"], "veri": h.source["kind"],
            "simdi": {**_pred(p), "saat": clock.isoformat(timespec="seconds")},
            "varis_egrisi": h.curve(),
        })
    return {"hastaneler": out, "demo_konum": r.demo_location, "zaman": datetime.now().isoformat(timespec="seconds"),
            "kural": "Varıştaki bekleme: şu anki kuyruktan başlayıp yol süresi boyunca geçmişten bilinen saatlik geliş "
                     "hızı ve hekim çizelgesiyle 300 tekrarlı ileri simülasyon (%25/%50/%75)."}


@app.get("/api/hastane")
def hastane() -> dict:
    if not HOSPITAL_FILE.exists():
        raise HTTPException(404, "config/hastane.json bulunamadı")
    return json.loads(HOSPITAL_FILE.read_text(encoding="utf-8"))
