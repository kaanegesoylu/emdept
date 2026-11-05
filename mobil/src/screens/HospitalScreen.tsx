import React, { useEffect, useState } from 'react';
import { Linking, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';

import { api, defaultBaseUrl, getBaseUrl, Hospital, setBaseUrl } from '../api';
import { Bullet, Button, Card, EmergencyStrip, H2, Note, P } from '../components';
import { color, radius, space } from '../theme';

export default function HospitalScreen({ onPrivacy }: { onPrivacy: () => void }) {
  const [h, setH] = useState<Hospital | null>(null);
  const [url, setUrl] = useState('');
  const [showDev, setShowDev] = useState(false);

  useEffect(() => {
    api.hospital().then(setH).catch(() => setH(null));
    getBaseUrl().then(setUrl);
  }, []);

  const mapsQuery = h?.harita_sorgu || h?.adres;
  const mapsUrl = mapsQuery ? `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(mapsQuery)}` : null;

  return (
    <ScrollView contentContainerStyle={st.wrap}>
      <EmergencyStrip />

      <Card>
        <Text style={st.name}>{h?.ad || 'Hastane bilgisi henüz eklenmedi'}</Text>
        <P>{h?.birim || 'Acil Servis · Yeşil Alan'}</P>
        {h?.adres ? <P>{h.adres}</P> : <P muted>Adres, proje hastanesiyle anlaşma yapıldığında eklenecek.</P>}
        {h?.calisma_saatleri ? <P muted>Açık: {h.calisma_saatleri}</P> : null}
        {h?.santral_telefon ? <Text style={st.phone} selectable>Santral: {h.santral_telefon}</Text> : null}
        {mapsUrl && <Button title="Yol tarifi al" onPress={() => Linking.openURL(mapsUrl)} />}
      </Card>

      <Card>
        <H2>Yeşil alan nedir?</H2>
        <P>
          Acil serviste hastalar önce triyajda değerlendirilir ve durumun aciliyetine göre renk alır. Yeşil alan,
          hayati tehlikesi olmayan ve ayakta muayene edilebilen hastalar içindir. Bu uygulamadaki süreler yalnızca
          yeşil alan içindir.
        </P>
        <P>
          Triyaj kararını uygulama değil, sağlık çalışanı verir. Durumunuz daha acil bulunursa beklemeden alınırsınız.
        </P>
      </Card>

      <Card style={{ borderColor: '#f3c3c3' }}>
        <H2>Beklemeden 112’yi arayın ya da hemen başvurun</H2>
        <Bullet>Göğüs ağrısı ya da göğüste baskı hissi</Bullet>
        <Bullet>Nefes almakta zorlanma</Bullet>
        <Bullet>Yüzde kayma, kolda ya da bacakta ani güçsüzlük, konuşma bozukluğu</Bullet>
        <Bullet>Bilinç bulanıklığı, bayılma, nöbet</Bullet>
        <Bullet>Durmayan kanama, ciddi yaralanma, yanık</Bullet>
        <Bullet>Dudak ya da dilde şişme, yaygın döküntüyle birlikte nefes darlığı</Bullet>
        <Bullet>Kendinize zarar verme düşünceleri</Bullet>
        <P muted>Bu liste eksiksiz değildir. Emin değilseniz 112’yi arayın.</P>
      </Card>

      <Note>
        Acil olmayan sağlık sorunlarında aile hekiminiz de bir seçenektir; acil servisin yükünü azaltır ve sizi daha az
        bekletebilir.
      </Note>

      <Button title="Gizlilik ve bilgilendirme" kind="ghost" onPress={onPrivacy} />

      <Text style={st.dev} onPress={() => setShowDev((x) => !x)}>Geliştirici ayarları</Text>
      {showDev && (
        <Card>
          <P muted>Tahmin sunucusunun adresi (proje ekibi içindir).</P>
          <TextInput value={url} onChangeText={setUrl} autoCapitalize="none" autoCorrect={false} style={st.input}
            placeholder={defaultBaseUrl()} accessibilityLabel="Sunucu adresi" />
          <View style={{ flexDirection: 'row', gap: space.s }}>
            <View style={{ flex: 1 }}><Button title="Kaydet" onPress={() => setBaseUrl(url)} /></View>
            <View style={{ flex: 1 }}><Button title="Varsayılan" kind="ghost" onPress={async () => { await setBaseUrl(''); setUrl(await getBaseUrl()); }} /></View>
          </View>
        </Card>
      )}
    </ScrollView>
  );
}

const st = StyleSheet.create({
  wrap: { padding: space.l, gap: space.m, paddingBottom: space.xxl },
  name: { fontSize: 20, fontWeight: '700', color: color.ink },
  phone: { fontSize: 15, color: color.ink, fontVariant: ['tabular-nums'] },
  dev: { textAlign: 'center', color: color.muted, fontSize: 13, paddingVertical: space.s },
  input: { borderWidth: 1, borderColor: color.line, borderRadius: radius.s, padding: space.m, fontSize: 15, color: color.ink, backgroundColor: '#fff' },
});
