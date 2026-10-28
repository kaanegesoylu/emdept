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
4. Sağ üstteki çalıştırma listesinden **Panel (Streamlit)** seçip ▶ ile başlatın. Tarayıcıda `http://localhost:8501` açılır.
   Terminalden: `streamlit run app.py`
5. Testler: **Testler (pytest)** yapılandırması ya da `pytest`.

## Panel

| Sayfa | Ne yapar |
|---|---|
| Veri | Sentetik veri üretir ya da hastane dosyasını yükler; hekim çizelgesi (gece/gündüz/akşam ya da saat saat) |
| Yoğunluk | Saatlik geliş hızı λ, kullanım oranı ρ, gün × saat haritası; Poisson ve muayene süresi kontrolü |
| Karar | Hedef (ör. hastaların %90'ı 30 dk içinde) için saat başına gereken hekim; model–veri karşılaştırması; simülasyonla doğrulama |
| Canlı durum | ESP32 butonlarından (seri port) ya da simülasyondan anlık kuyruk |
| Yöntem | Formüller, varsayımlar, kaynaklar |

## Klasör yapısı

```
app.py                  Streamlit girişi (sayfa gezinmesi)
acil/                   Hesaplama çekirdeği (arayüzden bağımsız)
  queueing.py           Erlang C, M/G/c, hedef ve gereken hekim, Lag-SIPP
  simulation.py         Ayrık olay simülasyonu (FCFS, değişen çizelge)
  synthetic.py          Sentetik veri üreteci
  data_io.py            CSV/Excel okuma, sütun tahmini, tarih ayrıştırma, veri kontrolü
  analysis.py           Yoğunluk analizi, dağılım testleri, saatlik karar
  live.py               Canlı durum, ESP32 mesajları, seri port okuyucu
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

Görev eşlemesi öneridir; danışman toplantısında netleştirin.
