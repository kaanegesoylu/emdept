# Yeşil Alan Kuyruk Paneli

FENG 497 Bitirme Projesi · İzmir Ekonomi Üniversitesi · 2026-2027 Güz
**Queue-Based Waiting Time Estimation System for Hospital Emergency Departments**

Acil servis yeşil alanında saatlik hasta gelişlerini ölçer, M/M/c (Erlang C) modeliyle bekleme süresini hesaplar ve hedef bekleme süresi için saat başına gereken hekim sayısını önerir. Hastane verisi yokken kendi sentetik verisiyle çalışır; veri gelince CSV/Excel yüklenir ve her şey yeniden hesaplanır.

## Kurulum (PyCharm)

1. PyCharm → **Open** → bu klasörü (`feng497-acil`) seçin.
2. Sağ alttan yorumlayıcıyı seçin: **Add New Interpreter → Virtualenv**, Python 3.10 veya üstü.
3. PyCharm `requirements.txt` için kurulum önerir; **Install requirements** deyin. Ya da terminalde:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
4. Sağ üstteki çalıştırma listesinden **Paneli Başlat** seçip ▶ ile başlatın (IDE'de Python SDK ayarı gerekmez; `.venv` içindeki Streamlit'i çalıştırır). Tarayıcıda `http://localhost:8501` açılır.
   Terminalden: `./baslat.sh` (gerekirse `.venv`'i kendisi kurar) ya da `streamlit run app.py`.
5. Testler: **Testleri Çalıştır** yapılandırması ya da `pytest`.

## Panel

| Sayfa | Ne yapar |
|---|---|
| Veri | Sentetik veri üretir ya da hastane dosyasını yükler; hekim çizelgesi (gece/gündüz/akşam ya da saat saat) |
| Yoğunluk | Saatlik geliş hızı λ, kullanım oranı ρ, gün × saat haritası; Poisson ve muayene süresi kontrolü |
| Karar | Hedef (ör. hastaların %90'ı 30 dk içinde) için saat başına gereken hekim; model–veri karşılaştırması; simülasyonla doğrulama |
| Canlı durum | ESP32 butonlarından (seri port) ya da simülasyondan anlık kuyruk |
| Yöntem | Formüller, varsayımlar, kaynaklar |

## Hasta uygulaması (mobil)

Hasta tarafı ayrı bir Expo (React Native) uygulamasıdır: `mobil/`. Ekranlar: Şimdi (canlı tahmin), Karşılaştır (konum + yol + varıştaki bekleme), Ne zaman (geçmişe dayalı), Bildirim, Hastane.

1. **API Başlat** (sağ üstteki listeden) — tahminleri uygulamaya sunar: `http://<bilgisayar>:8000/docs`
2. **Mobil Uygulama** — Expo sunucusunu açar; telefonda **Expo Go** ile QR kodu okutun (aynı Wi-Fi).

Canlı tahmin hastane veritabanına (HBYS) anlık erişim varsayımıyla simülasyondan gelir; geçmişe dayalı tahmin yalnızca geçmiş kayıtları kullanır. Karşılaştırma demosundaki hastaneler kurgusaldır (`config/hastaneler.json`). Ayrıntılar: `mobil/README.md`.

## Klasör yapısı

```
app.py                  Streamlit girişi (sayfa gezinmesi)
acil/                   Hesaplama çekirdeği (arayüzden bağımsız)
  queueing.py           Erlang C, M/G/c, hedef ve gereken hekim, Lag-SIPP
  simulation.py         Ayrık olay simülasyonu (FCFS, değişen çizelge)
  synthetic.py          Sentetik veri üreteci
  data_io.py            CSV/Excel okuma, sütun tahmini, tarih ayrıştırma, veri kontrolü
  analysis.py           Yoğunluk analizi, dağılım testleri, saatlik karar
  live.py               Canlı durum, ESP32 mesajları, seri port ve HBYS (veritabanı) okuyucu
  predict.py            Hastaya gösterilen tahmin: canlı ve geçmişe dayalı
  forecast.py           Varış anındaki bekleme (yol süresi boyunca ileri simülasyon)
  routing.py            Yol süresi ve hastane öneri kuralı
api.py                  Hasta uygulaması için tahmin API'si (FastAPI)
config/                 Hastane bilgisi ve karşılaştırma demosu hastaneleri
mobil/                  Hasta uygulaması (Expo / React Native)
views/                  Streamlit sayfaları
tests/                  pytest testleri
data/                   Örnek veri; hastane dosyaları data/gercek/ (depoya girmez)
firmware/               ESP32 buton yazılımı (Arduino)
matlab/                 Erlang C çapraz kontrolü
```

## Gerçek veri geldiğinde

1. Dosyayı `data/gercek/` içine koyun.
2. Panelde **Veri → Hastane dosyası**, dosyayı seçin, sütunları kontrol edip **Veriyi uygula**.
3. Hekim çizelgesini hastanenin gerçek çizelgesiyle güncelleyin (elle ya da `saat;hekim_sayisi` dosyasıyla).

Gerekli sütunlar için `data/README.md`. Kimlik, tanı, tedavi ve personel bilgisi gerekmez; yalnızca zaman damgaları kullanılır.

## ESP32

`firmware/esp32_butonlar/esp32_butonlar.ino` dosyasını Arduino IDE ile ESP32'ye yükleyin. Beş buton (GPIO 13, 12, 14, 27, 26 → GND) her basışta seri porta bir satır gönderir:

```json
{"device":"esp32-yesil-01","event":"arrival","ms":123456}
```

`event`: `arrival` (geliş) · `start` (muayeneye alındı) · `end` (muayene bitti) · `doctor_on` · `doctor_off`.
Panelde **Canlı durum → ESP32 (seri port)**, portu seçip **Bağlan**. Zaman damgasını Python yazar.

## MATLAB çapraz kontrolü

`matlab/erlang_c_kontrol.m`. Python testleriyle aynı vakalar:

| Vaka | Beklenen |
|---|---|
| C(2, 1) | 0,3333 |
| λ = 8, μ = 5, c = 2 → W_q | 21,33 dk |
| P(W ≤ 30 dk) | 0,738 |
| %90 hasta 30 dk içinde → gereken hekim | 3 |

## Ekip

| Kişi | Bölüm | Bu depoda |
|---|---|---|
| Kaan Ege Soylu | Bilgisayar Müh. | Yürütücü; `acil/synthetic.py`, `acil/analysis.py` |
| Ant Efe Kaynarcalı | Bilgisayar Müh. | Veri okuma ve Poisson kontrolü: `acil/data_io.py`, testler |
| Ece Günal | Yazılım Müh. | Panel ve mimari: `app.py`, `views/` |
| Kardelen Baysal | Endüstri Müh. | Hedef değerler ve literatür parametreleri; `Target` varsayılanları |
| Bora Azad Günay | Mekatronik Müh. | MATLAB doğrulaması: `matlab/` |
| Murat Çamlıca | Mekatronik Müh. | ESP32: `firmware/`, `acil/live.py` |


