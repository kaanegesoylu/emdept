import React from 'react';
import { ScrollView, StyleSheet, Text } from 'react-native';

import { Bullet, Button, Card, H2, Note, P } from '../components';
import { color, space } from '../theme';

/** Gizlilik, KVKK ve sorumluluk bilgilendirmesi. İlk açılışta ve Hastane sekmesinden gösterilir. */
export default function PrivacyScreen({ onClose, first }: { onClose: () => void; first?: boolean }) {
  return (
    <ScrollView contentContainerStyle={st.wrap}>
      <Text style={st.title} accessibilityRole="header">{first ? 'Başlamadan önce' : 'Gizlilik ve bilgilendirme'}</Text>

      <Note tone="warn">
        Hayati tehlike varsa uygulamaya bakmadan 112’yi arayın. Uygulama tıbbi değerlendirme yapmaz ve triyajın yerini
        tutmaz.
      </Note>

      <Card>
        <H2>Tahminler hakkında</H2>
        <Bullet>Gösterilen süreler tahmindir; kesin bir söz değildir. Aralık, hastaların yarısının bu sürede muayeneye alındığını gösterir.</Bullet>
        <Bullet>Muayene sırasını triyaj belirler. Daha acil bulunan hastalar önce alınır.</Bullet>
        <Bullet>Uzun bir tahmin, acile gitmemeniz için bir neden değildir.</Bullet>
        <Bullet>Bu uygulama bir öğrenci bitirme projesinin prototipidir. Hastane verisi paylaşılana kadar gösterilen süreler sentetik (üretilmiş) veriye dayanır ve bu her ekranda belirtilir.</Bullet>
      </Card>

      <Card>
        <H2>Kişisel verileriniz</H2>
        <Bullet>Uygulama ad, T.C. kimlik numarası, telefon, konum ya da sağlık bilgisi istemez ve toplamaz.</Bullet>
        <Bullet>Hesap, reklam ya da kullanım takibi yoktur.</Bullet>
        <Bullet>Bildirim eşiği gibi ayarlar yalnızca bu telefonda saklanır.</Bullet>
        <Bullet>Sunucuya giden istekler yalnızca gün ve saat içerir; sunucu erişim kaydı tutmaz.</Bullet>
        <Bullet>Tahminlerde kullanılan hastane verisi yalnızca anonim zaman damgalarından oluşur (kayıt, muayeneye alınma, muayene bitiş). 6698 sayılı KVKK md. 28/1-(b) kapsamında, anonim hâle getirilmiş verilerle yapılan araştırma niteliğindedir.</Bullet>
      </Card>

      <Card>
        <H2>Proje</H2>
        <P>
          FENG 497 Bitirme Projesi, İzmir Ekonomi Üniversitesi Mühendislik Fakültesi. Hastane acil servisi yeşil alanı
          için kuyruk tabanlı bekleme süresi tahmini.
        </P>
      </Card>

      <Button title={first ? 'Okudum, devam et' : 'Kapat'} onPress={onClose} />
    </ScrollView>
  );
}

const st = StyleSheet.create({
  wrap: { padding: space.l, gap: space.m, paddingBottom: space.xxl },
  title: { fontSize: 26, fontWeight: '800', color: color.ink, marginTop: space.s },
});
