"""Hastane karşılaştırma ve öneri kuralı.

Bu modül uygulamadaki (mobil/src/routing.ts) kuralın Python eşidir; testler ve rapor için.
Konum telefondan çıkmaz: aynı hesap telefonda yapılır.

Yol süresi (yaklaşık, trafik hariç)
  yol mesafesi  = kuş uçuşu mesafe × dolambaç katsayısı (araba 1,3 · yürüyüş 1,25)
  araba         = ilk 10 km 30 km/sa (şehir içi), sonrası 70 km/sa
  yürüyüş       = 4,5 km/sa; 5 km'den uzun yürüyüş önerilmez

Öneri kuralı
  1. Her hastane için varış anındaki bekleme tahmin edilir (acil/forecast.py).
  2. Toplam süre = yol + varıştaki bekleme (ortanca); belirsizlik = bekleme aralığının yarı genişliği.
  3. En yakın hastane her zaman temel alınır ve listede ilk gösterilir.
  4. Başka bir hastane ancak şu koşulların hepsi sağlanırsa önerilir:
       - toplam süre en yakındakinden en az 15 dk kısa,
       - bu kazanç iki hastanenin belirsizliklerinin toplamından büyük,
       - yol süresi 60 dakikayı geçmiyor.
  5. Hiçbiri sağlanmazsa en yakın hastane önerilir.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

MIN_SAVING_MIN = 15
MAX_TRAVEL_MIN = 60
DETOUR = {"araba": 1.3, "yuruyus": 1.25}
WALK_KMH = 4.5
WALK_MAX_KM = 5.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def travel_minutes(km_straight: float, mode: str) -> float | None:
    road = km_straight * DETOUR[mode]
    if mode == "yuruyus":
        return None if road > WALK_MAX_KM else road / WALK_KMH * 60
    city = min(road, 10.0)
    return (city / 30 + max(0.0, road - 10.0) / 70) * 60


def interp(curve: list[dict], minutes: float) -> tuple[float, float, float] | None:
    """Varış eğrisinden τ = minutes için (alt, orta, üst) — doğrusal ara değer."""
    pts = [c for c in curve if c["orta"] is not None]
    if not pts:
        return None
    if minutes >= pts[-1]["dakika"]:
        c = pts[-1]
        return c["alt"], c["orta"], c["ust"]
    for a, b in zip(pts, pts[1:]):
        if a["dakika"] <= minutes <= b["dakika"]:
            f = (minutes - a["dakika"]) / (b["dakika"] - a["dakika"])
            return tuple(a[k] + f * (b[k] - a[k]) for k in ("alt", "orta", "ust"))
    c = pts[0]
    return c["alt"], c["orta"], c["ust"]


@dataclass
class Option:
    id: str
    travel: float
    wait_lo: float
    wait_mid: float
    wait_hi: float

    @property
    def total(self) -> float:
        return self.travel + self.wait_mid

    @property
    def spread(self) -> float:
        return (self.wait_hi - self.wait_lo) / 2


def recommend(options: list[Option]) -> tuple[str, str]:
    """Döner: (önerilen hastane id, gerekçe)."""
    if not options:
        return "", "Karşılaştırılacak hastane yok."
    nearest = min(options, key=lambda o: o.travel)
    best, reason = nearest, "En yakın hastane; başka bir hastane belirgin bir kazanç sağlamıyor."
    for o in sorted(options, key=lambda o: o.total):
        if o is nearest:
            continue
        saving = nearest.total - o.total
        if (o.travel <= MAX_TRAVEL_MIN and saving >= MIN_SAVING_MIN
                and saving > nearest.spread + o.spread):
            best = o
            reason = (f"Toplam süre yaklaşık {round(saving)} dk daha kısa ve bu fark tahmin belirsizliğinden büyük.")
            break
    return best.id, reason
