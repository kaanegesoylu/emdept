import React, { useCallback, useEffect, useState } from 'react';
import { RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';

import { api, Prediction, Status } from '../api';
import { Card, EmergencyStrip, LevelChip, Note, P, SourceNote, timeAgo } from '../components';
import { color, radius, space } from '../theme';

const REFRESH_MS = 15000;
const STALE_MS = 2 * 60 * 1000;

export default function NowScreen({ status }: { status: Status | null }) {
  const [pred, setPred] = useState<Prediction | null>(null);
  const [fetchedAt, setFetchedAt] = useState<number>(0);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [, tick] = useState(0);

  const load = useCallback(async () => {
    try {
      setPred(await api.live());
      setFetchedAt(Date.now());
      setError(null);
    } catch (e) {
      setError('Güncel tahmin alınamadı. İnternet bağlantınızı kontrol edin.');
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(() => { load(); tick((x) => x + 1); }, REFRESH_MS);
    return () => clearInterval(id);
  }, [load]);

  const stale = !pred || Date.now() - fetchedAt > STALE_MS;
  const unavailable = !pred || pred.yontem === 'no_doctor' || pred.yontem === 'unavailable';

  return (
    <ScrollView
      contentContainerStyle={st.wrap}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={async () => { setRefreshing(true); await load(); setRefreshing(false); }} />}
    >
      <EmergencyStrip />

      <View style={st.hero} accessible accessibilityLabel={pred && !stale ? `Tahmini bekleme ${pred.metin}` : 'Tahmin yok'}>
        <Text style={st.heroTop}>Acil servis · Yeşil alan</Text>
        <Text style={st.heroTitle}>Şimdi gelseniz tahmini bekleme</Text>
        <Text style={st.heroTime} adjustsFontSizeToFit numberOfLines={1}>
          {stale ? '—' : pred!.metin}
        </Text>
        {!stale && !unavailable && (
          <View style={st.row}>
            <LevelChip value={pred!.duzey} />
            <Text style={st.heroInfo}>
              {pred!.bekleyen === 0 ? 'Sırada bekleyen yok' : `Sırada ${pred!.bekleyen} hasta`} · {pred!.hekim} hekim görevde
            </Text>
          </View>
        )}
        {!stale && unavailable && <Text style={st.heroInfo}>{pred!.dayanak}</Text>}
      </View>

      {error && <Note tone="warn">{error}</Note>}
      {stale && !error && <Note tone="warn">Tahmin yükleniyor…</Note>}

      <SourceNote status={status} live />

      <Card>
        <P>
          Aralık, benzer durumdaki hastaların yarısının muayeneye alındığı süreyi gösterir. Kesin bir söz değildir;
          triyajda daha acil bulunan hastalar önce muayene edilir.
        </P>
        <P muted>Son güncelleme {pred?.saat ? timeAgo(pred.saat) : '—'} · Aşağı çekerek yenileyebilirsiniz.</P>
      </Card>

      <Note>
        Bu süre, acile gidip gitmemeye karar vermeniz için değildir. Kendinizi kötü hissediyorsanız bekleme süresine
        bakmadan başvurun. Yolda durumunuz kötüleşirse 112’yi arayın.
      </Note>
    </ScrollView>
  );
}

const st = StyleSheet.create({
  wrap: { padding: space.l, gap: space.m },
  hero: { backgroundColor: color.accent, borderRadius: radius.l, padding: space.xl, gap: 6 },
  heroTop: { color: '#ffffff', opacity: 0.85, fontSize: 12, letterSpacing: 1.6, textTransform: 'uppercase', fontWeight: '600' },
  heroTitle: { color: '#ffffff', fontSize: 19, fontWeight: '600', marginTop: 4 },
  heroTime: { color: '#ffffff', fontSize: 46, fontWeight: '800', letterSpacing: -1, marginVertical: 6, fontVariant: ['tabular-nums'] },
  heroInfo: { color: '#ffffff', fontSize: 15, opacity: 0.95, flexShrink: 1 },
  row: { flexDirection: 'row', alignItems: 'center', gap: space.m, flexWrap: 'wrap' },
});
