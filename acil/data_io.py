"""Hastane dosyalarını okuma: CSV/Excel, sütun tahmini, tarih ayrıştırma, veri kontrolü.

Yalnızca zaman damgaları kullanılır; kimlik, tanı ve personel bilgisi gerekmez.
"""
from __future__ import annotations

import datetime as dt
import io
import re
import unicodedata
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

FIELDS = {
    "arrival": "Kayıt / geliş saati",
    "start": "Muayeneye alınma",
    "end": "Muayene bitiş",
    "exit": "Çıkış",
    "date": "Ayrı tarih sütunu",
}

_PATTERNS = {
    "arrival": r"(kayit|gelis|giris|basvuru|arrival|triaj|triage)",
    "start": r"(muayene(ye)? ?(alin|bas|start)|exam ?start|seen|doktor ?gor|hekim ?gor)",
    "end": r"(muayene ?(bit|son|end)|exam ?end|sonuclan)",
    "exit": r"(cikis|taburcu|exit|discharge|ayrilis)",
    "date": r"^(tarih|date|gun)$",
}
_TIME_ONLY = re.compile(r"^\d{1,2}[:.]\d{2}([:.]\d{2})?$")
_ISO = re.compile(r"^\d{4}-\d{1,2}-\d{1,2}")


def normalize(s: object) -> str:
    s = str(s).replace("ı", "i").replace("İ", "i").lower()
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def read_table(data: bytes, name: str) -> dict[str, pd.DataFrame]:
    """Dosyayı sayfa adı → DataFrame (tüm hücreler ham) sözlüğü olarak okur."""
    if name.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(data), sheet_name=None, dtype=object)
    for enc in ("utf-8-sig", "cp1254", "latin-1"):
        try:
            text = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    df = pd.read_csv(io.StringIO(text), sep=None, engine="python", dtype=str, skip_blank_lines=True)
    return {"CSV": df}


def guess_columns(columns: list[str]) -> dict[str, str | None]:
    norm = [normalize(c) for c in columns]
    out: dict[str, str | None] = {}
    for key, pat in _PATTERNS.items():
        idx = next((i for i, c in enumerate(norm) if re.search(pat, c)), None)
        out[key] = columns[idx] if idx is not None else None
    for k in ("start", "end", "exit"):
        if out[k] == out["arrival"]:
            out[k] = None
    return out


def _parse_dates(s: pd.Series) -> pd.Series:
    """Tarih(+saat) sütununu Timestamp'e çevirir; okunamayan NaT olur."""
    if pd.api.types.is_datetime64_any_dtype(s):
        return s.dt.round("s")
    if pd.api.types.is_numeric_dtype(s):  # Excel seri numarası
        return pd.to_datetime(s, unit="D", origin="1899-12-30", errors="coerce").dt.round("s")
    out = pd.Series(pd.NaT, index=s.index, dtype="datetime64[ns]")
    for i, v in s.items():
        if v is None or (isinstance(v, float) and np.isnan(v)):
            continue
        if isinstance(v, (pd.Timestamp, dt.datetime)):
            out[i] = pd.Timestamp(v).round("s")
            continue
        if isinstance(v, dt.date):
            out[i] = pd.Timestamp(v)
            continue
        if isinstance(v, (int, float)) and 20000 < v < 80000:
            out[i] = (pd.Timestamp("1899-12-30") + pd.to_timedelta(v, unit="D")).round("s")
            continue
        txt = str(v).strip()
        if not txt:
            continue
        ts = pd.to_datetime(txt, dayfirst=not _ISO.match(txt), errors="coerce")
        if ts is not pd.NaT and not pd.isna(ts):
            out[i] = ts
    return out


def _parse_times(s: pd.Series) -> pd.Series:
    """Yalnız saat sütunu (14:05, datetime.time, gün kesri) → Timedelta."""
    out = pd.Series(pd.NaT, index=s.index, dtype="timedelta64[ns]")
    for i, v in s.items():
        if isinstance(v, dt.time):
            out[i] = pd.Timedelta(hours=v.hour, minutes=v.minute, seconds=v.second)
        elif isinstance(v, (int, float)) and not np.isnan(v) and 0 <= v < 1:
            out[i] = pd.Timedelta(seconds=round(v * 86400))
        elif isinstance(v, str) and _TIME_ONLY.match(v.strip()):
            parts = [int(x) for x in re.split(r"[:.]", v.strip())]
            if parts[0] < 24:
                out[i] = pd.Timedelta(hours=parts[0], minutes=parts[1], seconds=parts[2] if len(parts) > 2 else 0)
    return out


def _is_time_only(s: pd.Series) -> bool:
    vals = s.dropna()
    vals = vals[vals.astype(str).str.strip() != ""]
    if vals.empty:
        return False
    hits = sum(isinstance(v, dt.time) or (isinstance(v, str) and bool(_TIME_ONLY.match(v.strip())))
               or (isinstance(v, (int, float)) and 0 <= v < 1) for v in vals)
    return hits / len(vals) > 0.8


@dataclass
class LoadReport:
    total: int = 0
    valid: int = 0
    no_arrival: int = 0
    start_before_arrival: int = 0
    end_before_start: int = 0
    exit_before_arrival: int = 0
    long_wait: int = 0
    midnight_fixed: int = 0

    def messages(self) -> list[str]:
        m = []
        if self.no_arrival:
            m.append(f"{self.no_arrival} satırda kayıt saati okunamadı")
        if self.start_before_arrival:
            m.append(f"{self.start_before_arrival} satırda muayene kayıttan önce")
        if self.end_before_start:
            m.append(f"{self.end_before_start} satırda bitiş başlangıçtan önce")
        if self.exit_before_arrival:
            m.append(f"{self.exit_before_arrival} satırda çıkış kayıttan önce")
        if self.long_wait:
            m.append(f"{self.long_wait} satırda bekleme 24 saati aşıyor")
        if self.midnight_fixed:
            m.append(f"{self.midnight_fixed} saat gece yarısı geçişi olarak düzeltildi")
        return m


def build_patients(df: pd.DataFrame, mapping: dict[str, str | None]) -> tuple[pd.DataFrame, LoadReport]:
    """Ham tabloyu standart hasta tablosuna (arrival, start, end, exit) çevirir."""
    rep = LoadReport(total=len(df))
    date = _parse_dates(df[mapping["date"]]) if mapping.get("date") else None

    def col(key: str) -> pd.Series:
        name = mapping.get(key)
        if not name:
            return pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
        s = df[name]
        if _is_time_only(s):
            if date is None:
                return pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
            return date.dt.normalize() + _parse_times(s)
        return _parse_dates(s)

    out = pd.DataFrame({k: col(k) for k in ("arrival", "start", "end", "exit")})
    rep.no_arrival = int(out["arrival"].isna().sum())
    out = out.dropna(subset=["arrival"]).copy()

    six_h, day = pd.Timedelta(hours=6), pd.Timedelta(days=1)

    def roll(t: pd.Series, ref: pd.Series) -> pd.Series:
        need = t.notna() & ref.notna() & (ref - t > six_h)
        rep.midnight_fixed += int(need.sum())
        return t.where(~need, t + day)

    out["start"] = roll(out["start"], out["arrival"])
    out["end"] = roll(out["end"], out["start"].fillna(out["arrival"]))
    out["exit"] = roll(out["exit"], out["end"].fillna(out["start"]).fillna(out["arrival"]))

    bad = out["start"] < out["arrival"]
    rep.start_before_arrival = int(bad.sum()); out.loc[bad, "start"] = pd.NaT
    bad = out["end"] < out["start"]
    rep.end_before_start = int(bad.sum()); out.loc[bad, "end"] = pd.NaT
    bad = out["exit"] < out["arrival"]
    rep.exit_before_arrival = int(bad.sum()); out.loc[bad, "exit"] = pd.NaT
    bad = (out["start"] - out["arrival"]) > day
    rep.long_wait = int(bad.sum()); out.loc[bad, "start"] = pd.NaT

    out = out.sort_values("arrival").reset_index(drop=True)
    rep.valid = len(out)
    return out, rep


def load_staffing(df: pd.DataFrame) -> list[int] | None:
    """Saatlik hekim çizelgesi: 'saat' ve 'hekim_sayisi' sütunları → 24 saatlik ortalama (yuvarlanmış)."""
    norm = {normalize(c): c for c in df.columns}
    hcol = next((c for n, c in norm.items() if re.search(r"(saat|hour|zaman|time)", n)), None)
    ccol = next((c for n, c in norm.items() if re.search(r"(hekim|doktor|physician|doctor|sayi|count)", n)), None)
    if hcol is None or ccol is None:
        return None
    hours = []
    for v in df[hcol]:
        if isinstance(v, (dt.time, dt.datetime, pd.Timestamp)):
            hours.append(v.hour)
            continue
        txt = str(v).strip()
        m = re.match(r"^(\d{1,2})(?:[:.]\d{2})?", txt)
        hours.append(int(m.group(1)) if m and int(m.group(1)) < 24 else None)
    counts = pd.to_numeric(df[ccol].astype(str).str.replace(",", "."), errors="coerce")
    t = pd.DataFrame({"h": hours, "c": counts}).dropna()
    if t.empty:
        return None
    avg = t.groupby("h")["c"].mean()
    return [int(round(avg.get(h, 0))) for h in range(24)]
