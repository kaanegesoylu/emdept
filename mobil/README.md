# Yeşil Alan — hasta uygulaması (Expo)

Hastanın telefonu için: şu anki tahmini bekleme, hastane karşılaştırma (yol + varıştaki bekleme),
geçmişe dayalı "ne zaman gitmeli" tablosu, bekleme azalınca bildirim, hastane ve gizlilik bilgisi.

## Çalıştırma

1. Önce API'yi başlatın (proje kökünde): `./.venv/bin/uvicorn api:app --host 0.0.0.0 --port 8000 --no-access-log`
   ya da IDE'de **API Başlat**.
2. Bu klasörde bir kez `npm install`, sonra `npx expo start` (IDE'de **Mobil Uygulama**).
3. Telefona **Expo Go** uygulamasını kurun, terminaldeki QR kodu okutun. Telefon ve bilgisayar aynı Wi-Fi ağında olmalı.
   Uygulama API adresini kendisi bulur (Expo sunucusunun çalıştığı bilgisayarın 8000 portu).
   Gerekirse Hastane → Geliştirici ayarları'ndan elle girilir.
4. Tarayıcıda denemek için: `npx expo start --web`.

## Etik ve gizlilik

- Kişisel veri toplanmaz; hesap, reklam, analitik yok.
- Konum yalnızca "Konumum" seçilirse istenir ve telefondan çıkmaz: telefon hastanelerin varış eğrilerini indirir,
  yol süresini ve öneriyi kendisi hesaplar (`src/routing.ts`).
- Her ekranda 112 şeridi; tahmin kesin söz değildir, triyajın yerini tutmaz; uzun tahmin acile gitmemek için neden değildir.
- Veri kaynağı (sentetik / gerçek, kurgusal hastane) her ekranda yazılır.
- Bildirim yereldir, en fazla 3 saat takip eder, acil durum uyarısı değildir.

## Klasörler

- `App.tsx` — sekmeler, ilk açılış bilgilendirmesi
- `src/screens/` — Şimdi, Karşılaştır, Ne zaman, Bildirim, Hastane, Gizlilik
- `src/routing.ts` — yol süresi ve öneri kuralı (Python eşi: `acil/routing.py`)
- `src/notify.ts` — yerel bildirim
- `src/api.ts` — API istemcisi
