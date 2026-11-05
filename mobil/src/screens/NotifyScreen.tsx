import React from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { Button, Card, EmergencyStrip, H2, Note, P } from '../components';
import { notificationsSupported, THRESHOLDS, useWaitWatcher } from '../notify';
import { color, radius, space } from '../theme';

export default function NotifyScreen({ watcher }: { watcher: ReturnType<typeof useWaitWatcher> }) {
  const { state, start, stop, setThreshold } = watcher;
  return (
    <ScrollView contentContainerStyle={st.wrap}>
      <EmergencyStrip />
      <Card>
        <H2>Bekleme azalınca haber ver</H2>
        <P>Tahmini bekleme seçtiğiniz sürenin altına indiğinde telefonunuza bir bildirim gelir.</P>
        <View style={st.opts}>
          {THRESHOLDS.map((t) => (
            <Pressable key={t} onPress={() => setThreshold(t)} disabled={state.active}
              style={[st.opt, state.threshold === t && st.optOn, state.active && { opacity: 0.6 }]}
              accessibilityRole="radio" accessibilityState={{ selected: state.threshold === t }}>
              <Text style={[st.optText, state.threshold === t && { color: '#fff' }]}>{t} dk</Text>
            </Pressable>
          ))}
        </View>
        {notificationsSupported ? (
          state.active ? (
            <>
              <Text style={st.active}>Takip ediliyor · eşik {state.threshold} dk{state.lastMid !== null ? ` · şu an ortanca ${Math.round(state.lastMid)} dk` : ''}</Text>
              <Button title="Takibi durdur" kind="ghost" onPress={stop} />
            </>
          ) : (
            <Button title="Takibi başlat" onPress={start} />
          )
        ) : (
          <P muted>Bildirimler yalnızca telefonda çalışır.</P>
        )}
        {state.message && <P>{state.message}</P>}
      </Card>

      <Note tone="warn">
        Bildirim bir acil durum uyarısı değildir ve gecikebilir. Durumunuz kötüleşirse bildirimi beklemeyin.
      </Note>

      <Card>
        <H2>Nasıl çalışır?</H2>
        <P>
          Uygulama açıkken her 30 saniyede bir güncel tahmine bakar. Telefon uygulamayı arka planda uzun süre
          durdurursa bildirim gecikebilir. Takip en fazla 3 saat sürer, sonra kendiliğinden durur.
        </P>
        <P>
          Seçtiğiniz süre yalnızca bu telefonda saklanır. Sunucuya kim olduğunuz, nerede olduğunuz ya da ne zaman
          geleceğiniz bildirilmez.
        </P>
      </Card>
    </ScrollView>
  );
}

const st = StyleSheet.create({
  wrap: { padding: space.l, gap: space.m },
  opts: { flexDirection: 'row', gap: space.s, marginVertical: space.s },
  opt: { flex: 1, paddingVertical: 12, alignItems: 'center', borderRadius: radius.s, borderWidth: 1, borderColor: color.line, backgroundColor: '#fff' },
  optOn: { backgroundColor: color.accent, borderColor: color.accent },
  optText: { fontWeight: '700', color: color.ink, fontSize: 15 },
  active: { color: color.accent, fontWeight: '600', fontSize: 14 },
});
