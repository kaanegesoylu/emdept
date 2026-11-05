"""Canlı durum: ESP32 buton olaylarından anlık kuyruk durumu.

Olay tabanlı tasarım: her buton modelin bir değişkenini ölçer.
  arrival    → geliş hızı λ
  start      → bekleme süresi W_q
  end        → hizmet süresi (μ)
  doctor_on / doctor_off → aktif hekim sayısı c

ESP32 her basışta seri porttan bir JSON satırı gönderir:
  {"device":"esp32-yesil-01","event":"arrival"}
Zaman damgası (ts) yoksa Python alındığı anı yazar.
"""
from __future__ import annotations

import json
import math
import queue
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np

from .queueing import queue_stats

EVENTS = ("arrival", "start", "end", "doctor_on", "doctor_off")


def parse_message(line: str, now: datetime | None = None) -> tuple[str, datetime] | None:
    """Bir JSON satırını (olay, zaman) ikilisine çevirir; geçersizse None."""
    try:
        msg = json.loads(line)
    except (json.JSONDecodeError, TypeError):
        return None
    ev = msg.get("event")
    if ev not in EVENTS:
        return None
    ts = msg.get("ts")
    try:
        t = datetime.fromisoformat(ts) if ts else (now or datetime.now())
    except ValueError:
        t = now or datetime.now()
    return ev, t


@dataclass
class LiveState:
    doctors: int = 2
    waiting: deque = field(default_factory=deque)      # bekleyenlerin geliş zamanları
    in_service: int = 0
    arrivals: deque = field(default_factory=deque)     # son 60 dk gelişleri
    waits: deque = field(default_factory=deque)        # (zaman, bekleme dk)
    history: deque = field(default_factory=lambda: deque(maxlen=2000))  # (zaman, bekleyen)
    log: deque = field(default_factory=lambda: deque(maxlen=200))
    now: datetime = field(default_factory=datetime.now)

    def apply(self, event: str, t: datetime, device: str = "esp32-yesil-01") -> bool:
        """Olayı uygular. Uygulanamazsa (ör. bekleyen yokken 'start') False döner."""
        self.now = max(self.now, t)
        extra = ""
        if event == "arrival":
            self.waiting.append(t)
            self.arrivals.append(t)
        elif event == "start":
            if not self.waiting or self.in_service >= self.doctors:
                return False
            a = self.waiting.popleft()
            w = (t - a).total_seconds() / 60
            self.waits.append((t, w))
            self.in_service += 1
            extra = f',"wait_min":{w:.1f}'
        elif event == "end":
            if self.in_service == 0:
                return False
            self.in_service -= 1
        elif event == "doctor_on":
            self.doctors += 1
            extra = f',"active":{self.doctors}'
        elif event == "doctor_off":
            if self.doctors == 0:
                return False
            self.doctors -= 1
            extra = f',"active":{self.doctors}'
        self.log.append(f'{{"device":"{device}","event":"{event}","ts":"{t.isoformat(timespec="seconds")}"{extra}}}')
        self._trim()
        return True

    def _trim(self) -> None:
        cut = self.now - timedelta(hours=1)
        while self.arrivals and self.arrivals[0] < cut:
            self.arrivals.popleft()
        while self.waits and self.waits[0][0] < cut:
            self.waits.popleft()
        self.history.append((self.now, len(self.waiting)))

    def expected_wait_min(self, mu: float) -> float:
        """Şimdi gelen bir hastanın beklenen beklemesi (üstel hizmet, FCFS)."""
        if self.doctors <= 0:
            return math.inf
        free = self.doctors - self.in_service
        if free > 0 and not self.waiting:
            return 0.0
        ahead = len(self.waiting) + 1 - max(0, free)
        return max(0.0, ahead / (self.doctors * mu) * 60)

    def model_wait_min(self, lam: float, mu: float) -> float:
        return queue_stats(lam, mu, self.doctors).wq_min


class Simulator:
    """ESP32 yokken olay üretir: saatlik λ ile geliş, μ ile muayene, çizelgeye göre hekim."""

    def __init__(self, lam_h: list[float], mu: float, staffing: list[int], seed: int = 2026):
        self.lam_h, self.mu, self.staffing = lam_h, mu, staffing
        self.rng = np.random.default_rng(seed)
        self.busy_until: list[datetime] = []
        self.last_hour: int | None = None

    def advance(self, st: LiveState, seconds: float) -> None:
        end = st.now + timedelta(seconds=seconds)
        while True:
            h = st.now.hour
            if h != self.last_hour:
                self.last_hour = h
                target = int(self.staffing[h])
                while st.doctors < target:
                    st.apply("doctor_on", st.now)
                while st.doctors > target:
                    st.apply("doctor_off", st.now)
            lam = self.lam_h[h]
            next_arr = st.now + timedelta(hours=self.rng.exponential(1 / lam)) if lam > 0 else datetime.max
            next_end = min(self.busy_until) if self.busy_until else datetime.max
            next_hour = (st.now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            t = min(next_arr, next_end, next_hour, end)
            if t == end and t < min(next_arr, next_end):
                st.now = end
                st._trim()
                break
            st.now = t
            if t == next_end:
                self.busy_until.remove(t)
                st.apply("end", t, "simulasyon")
            elif t == next_arr:
                st.apply("arrival", t, "simulasyon")
            self._start_waiting(st)
            if t >= end:
                break

    def _start_waiting(self, st: LiveState) -> None:
        while st.waiting and st.in_service < st.doctors:
            st.apply("start", st.now, "simulasyon")
            self.busy_until.append(st.now + timedelta(hours=self.rng.exponential(1 / self.mu)))


class SerialSource:
    """ESP32'yi seri porttan okur (pyserial gerekir). Olaylar thread-güvenli kuyruğa düşer."""

    def __init__(self, port: str, baud: int = 115200):
        import serial  # pyserial
        self.ser = serial.Serial(port, baud, timeout=1)
        self.events: queue.Queue = queue.Queue()
        self.alive = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self) -> None:
        while self.alive:
            try:
                line = self.ser.readline().decode("utf-8", "ignore").strip()
            except Exception:
                break
            if line:
                parsed = parse_message(line)
                if parsed:
                    self.events.put(parsed)

    def drain(self, st: LiveState) -> int:
        n = 0
        while not self.events.empty():
            ev, t = self.events.get_nowait()
            st.apply(ev, t, "esp32")
            n += 1
        return n

    def close(self) -> None:
        self.alive = False
        try:
            self.ser.close()
        except Exception:
            pass


def list_serial_ports() -> list[str]:
    try:
        from serial.tools import list_ports
        return [p.device for p in list_ports.comports()]
    except Exception:
        return []


class DatabaseSource:
    """Hastane veritabanından (HBYS) olay okuyucu — gerçek erişim olduğunda simülasyonun yerine geçer.

    Bugün hastane veritabanına erişim yok; panelin simülasyon modu tam olarak bu sınıfın
    üreteceği akışı taklit eder. Erişim sağlanırsa hastane BT birimiyle anlaşılan salt okunur bir
    görünüm (view) şu sütunları vermelidir:  id (artan), event, ts
      event ∈ arrival | start | end | doctor_on | doctor_off
    Kimlik, tanı veya personel bilgisi gerekmez.

    conn: herhangi bir DB-API 2.0 bağlantısı (sqlite3, psycopg, pyodbc …).
    query: parametre biçimi sürücüye göre değişir (sqlite3 için '?', psycopg için '%s').
    """

    DEFAULT_QUERY = "SELECT id, event, ts FROM yesil_alan_olaylar WHERE id > ? ORDER BY id"

    def __init__(self, conn, query: str = DEFAULT_QUERY, last_id: int = 0):
        self.conn, self.query, self.last_id = conn, query, last_id

    def drain(self, st: LiveState) -> int:
        cur = self.conn.cursor()
        cur.execute(self.query, (self.last_id,))
        n = 0
        for row_id, event, ts in cur.fetchall():
            self.last_id = max(self.last_id, int(row_id))
            if event not in EVENTS:
                continue
            t = ts if isinstance(ts, datetime) else datetime.fromisoformat(str(ts))
            st.apply(event, t, "hbys")
            n += 1
        return n
