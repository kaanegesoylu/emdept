# Veri klasörü

- `ornek_hasta_verisi.csv` — sentetik örnek (28 gün, ~3.250 hasta). Hastane verisi değildir; dosya biçimini denemek için.
- `ornek_hekim_cizelgesi.csv` — saatlik hekim çizelgesi örneği (`saat;hekim_sayisi`).
- `gercek/` — hastaneden gelen dosyaları buraya koyun. Bu klasör `.gitignore` ile depoya girmez.

Beklenen sütunlar (adlar serbest, panel tahmin eder):

| Sütun | Zorunlu | Ne için |
|---|---|---|
| kayıt / geliş saati | evet | saatlik geliş hızı λ |
| muayeneye alınma | önerilir | gerçek bekleme süresi, model doğrulaması |
| muayene bitiş | önerilir | hekim hizmet süresi μ |
| çıkış | isteğe bağlı | toplam kalış süresi (tetkik dahil) |

Tarih biçimi `05.01.2026 14:23` ya da `2026-01-05 14:23`. Tarih ve saat ayrı sütunlardaysa panelde “Ayrı tarih sütunu” seçilir.
