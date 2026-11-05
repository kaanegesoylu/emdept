import React, { useEffect, useMemo, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { api, Cell, Prediction, Status, todayIndex } from '../api';
import { Card, EmergencyStrip, H2, Note, P, SourceNote } from '../components';
import { color, DAYS, DAYS_LONG, radius, space } from '../theme';

/** Geçmişe dayalı tahmin: anlık veri kullanılmaz, yalnızca aynı gün ve saatteki geçmiş kayıtlar. */
export default function WhenScreen({ status }: { status: Status | null }) {
  const [cells, setCells] = useState<Cell[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [day, setDay] = useState(todayIndex());
  const [hour, setHour] = useState(new Date().getHours());
  const [detail, setDetail] = useState<Prediction | null>(null);

  useEffect(() => {
    api.week().then((r) => { setCells(r.hucreler); setError(null); }).catch(() => setError('Geçmiş tahminler alınamadı.'));
  }, []);

  useEffect(() => {
    setDetail(null);
    api.history(day, hour).then(setDetail).catch(() => setDetail(null));
  }, [day, hour]);

  const rows = useMemo(() => (cells ?? []).filter((c) => c.gun === day).sort((a, b) => a.saat - b.saat), [cells, day]);
  const max = useMemo(() => Math.max(10, ...rows.map((r) => r.ust_dk ?? 0)), [rows]);
  // Gündüz-akşam saatleri içinde en sakin üç saat (gece yarısından sonrası önerilmez)
  const calm = useMemo(() => {
    const day_ = rows.filter((r) => r.saat >= 8 && r.saat <= 22 && r.orta_dk !== null);
    return new Set([...day_].sort((a, b) => (a.orta_dk! - b.orta_dk!)).slice(0, 3).map((r) => r.saat));
  }, [rows]);
  const now = new Date();

  return (
    <ScrollView contentContainerStyle={st.wrap}>
      <EmergencyStrip />
      <Note tone="warn">
        Bu sayfa acil olmayan durumlar içindir. Acil bir durumda saat seçmeyin, hemen başvurun.
      </Note>

      <View style={st.days} accessibilityRole="tablist">
        {DAYS.map((d, i) => (
          <Pressable key={d} onPress={() => setDay(i)} style={[st.day, i === day && st.dayOn]}
            accessibilityRole="tab" accessibilityState={{ selected: i === day }} accessibilityLabel={DAYS_LONG[i]}>
            <Text style={[st.dayText, i === day && st.dayTextOn]}>{d}</Text>
            {i === todayIndex(now) && <Text style={[st.today, i === day && { color: '#fff' }]}>bugün</Text>}
          </Pressable>
        ))}
      </View>

      <Card>
        <Text style={st.detailHead}>{DAYS_LONG[day]} {String(hour).padStart(2, '0')}:00–{String((hour + 1) % 24).padStart(2, '0')}:00</Text>
        <Text style={st.detailTime}>{detail ? detail.metin : '…'}</Text>
        <P muted>{detail?.dayanak ?? ''}</P>
      </Card>

      <SourceNote status={status} />
      {error && <Note tone="warn">{error}</Note>}

      <Card style={{ paddingHorizontal: space.m }}>
        <H2>Saatlere göre tipik bekleme</H2>
        <P muted>Çubuk: hastaların yarısının düştüğü aralık. Çizgi: ortanca. Bir saate dokunun.</P>
        <View style={{ gap: 2, marginTop: space.s }}>
          {rows.map((r) => {
            const lo = r.alt_dk ?? 0, hi = r.ust_dk ?? 0, mid = r.orta_dk ?? 0;
            const sel = r.saat === hour;
            return (
              <Pressable key={r.saat} onPress={() => setHour(r.saat)} style={[st.hr, sel && st.hrSel]}
                accessibilityLabel={`${r.saat}:00, ortanca ${Math.round(mid)} dakika`}>
                <Text style={[st.hrLabel, sel && { color: color.ink, fontWeight: '700' }]}>{String(r.saat).padStart(2, '0')}:00</Text>
                <View style={st.track}>
                  {r.ust_dk === null ? (
                    <Text style={st.na}>tahmin yok</Text>
                  ) : (
                    <>
                      <View style={[st.bar, { left: `${(lo / max) * 100}%`, width: `${Math.max(1.5, ((hi - lo) / max) * 100)}%` }]} />
                      <View style={[st.mid, { left: `${(mid / max) * 100}%` }]} />
                    </>
                  )}
                </View>
                <Text style={st.hrVal}>{r.orta_dk === null ? '–' : `${Math.round(mid)} dk`}</Text>
                <Text style={st.calm}>{calm.has(r.saat) ? 'sakin' : ''}</Text>
              </Pressable>
            );
          })}
          {!cells && !error && <P muted>Yükleniyor…</P>}
        </View>
      </Card>

      <Card>
        <H2>Bu tahmin nasıl yapılıyor?</H2>
        <P>
          Anlık veri kullanılmaz. Seçtiğiniz gün ve saatte geçmişte gelen hastaların muayeneye alınana kadar ne kadar
          beklediğine bakılır. O saat için yeterli kayıt yoksa geçmişteki hasta sayısı ve hekim sayısıyla kuyruk modeli
          (Erlang C) kullanılır. Geçmiş, bugünün aynısı olmayabilir: salgın dönemleri, bayramlar ve kazalar bekleme
          süresini değiştirir.
        </P>
      </Card>
    </ScrollView>
  );
}

const st = StyleSheet.create({
  wrap: { padding: space.l, gap: space.m },
  days: { flexDirection: 'row', gap: 6 },
  day: { flex: 1, alignItems: 'center', paddingVertical: 8, borderRadius: radius.s, backgroundColor: color.card, borderWidth: 1, borderColor: color.line },
  dayOn: { backgroundColor: color.accent, borderColor: color.accent },
  dayText: { fontWeight: '700', color: color.ink, fontSize: 14 },
  dayTextOn: { color: '#fff' },
  today: { fontSize: 10, color: color.muted, marginTop: 1 },
  detailHead: { fontSize: 14, color: color.ink2, fontWeight: '600' },
  detailTime: { fontSize: 34, fontWeight: '800', color: color.ink, fontVariant: ['tabular-nums'] },
  hr: { flexDirection: 'row', alignItems: 'center', gap: space.s, paddingVertical: 5, paddingHorizontal: 6, borderRadius: radius.s },
  hrSel: { backgroundColor: color.accentSoft },
  hrLabel: { width: 44, fontSize: 13, color: color.ink2, fontVariant: ['tabular-nums'] },
  track: { flex: 1, height: 14, justifyContent: 'center' },
  bar: { position: 'absolute', height: 10, borderRadius: 5, backgroundColor: '#86b6ef' },
  mid: { position: 'absolute', width: 3, height: 14, borderRadius: 2, backgroundColor: '#184f95', marginLeft: -1 },
  na: { fontSize: 12, color: color.muted },
  hrVal: { width: 46, textAlign: 'right', fontSize: 13, color: color.ink, fontVariant: ['tabular-nums'] },
  calm: { width: 38, fontSize: 11, color: color.good, fontWeight: '700' },
});
