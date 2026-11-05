import * as Location from 'expo-location';
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Linking, Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';

import { api, HospitalsResponse } from '../api';
import { Bullet, Button, Card, EmergencyStrip, H2, Note, P } from '../components';
import { clockAfter, fmtDuration, fmtRange, haversineKm, interp, MAX_TRAVEL_MIN, MIN_SAVING_MIN, Mode, Option, recommend, travelMinutes } from '../routing';
import { color, radius, space } from '../theme';

type Where = { kind: 'none' } | { kind: 'gps' | 'demo'; lat: number; lon: number; label: string };

const REFRESH_MS = 60000;

export default function CompareScreen() {
  const [data, setData] = useState<HospitalsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [where, setWhere] = useState<Where>({ kind: 'none' });
  const [mode, setMode] = useState<Mode>('araba');
  const [locMsg, setLocMsg] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try { setData(await api.hospitals()); setError(null); }
    catch { setError('Hastane bilgileri alınamadı. Bağlantınızı kontrol edin.'); }
  }, []);

  useEffect(() => { load(); const id = setInterval(load, REFRESH_MS); return () => clearInterval(id); }, [load]);

  const useGps = async () => {
    setLocMsg(null);
    try {
      const perm = await Location.requestForegroundPermissionsAsync();
      if (!perm.granted) { setLocMsg('Konum izni verilmedi. Demo konumu kullanabilir ya da konumsuz devam edebilirsiniz.'); return; }
      const pos = (await Location.getLastKnownPositionAsync()) ?? (await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced }));
      setWhere({ kind: 'gps', lat: pos.coords.latitude, lon: pos.coords.longitude, label: 'Konumunuz' });
    } catch {
      setLocMsg('Konum alınamadı. Demo konumu kullanabilirsiniz.');
    }
  };

  const rows = useMemo(() => {
    if (!data) return [];
    return data.hastaneler.map((h) => {
      const km = where.kind === 'none' ? null : haversineKm(where.lat, where.lon, h.lat, h.lon);
      const travel = km === null ? null : travelMinutes(km, mode);
      const atArrival = travel === null ? null : interp(h.varis_egrisi, travel);
      return { h, km, travel, atArrival };
    });
  }, [data, where, mode]);

  const rec = useMemo(() => {
    const opts: Option[] = rows.filter((r) => r.travel !== null && r.atArrival)
      .map((r) => ({ id: r.h.id, travel: r.travel!, lo: r.atArrival![0], mid: r.atArrival![1], hi: r.atArrival![2] }));
    return opts.length ? recommend(opts) : null;
  }, [rows]);

  const nearestId = useMemo(() => {
    const w = rows.filter((r) => r.travel !== null);
    return w.length ? w.reduce((a, b) => (b.travel! < a.travel! ? b : a)).h.id : null;
  }, [rows]);

  const sorted = useMemo(() => {
    const key = (r: (typeof rows)[number]) => (r.travel !== null && r.atArrival ? r.travel + r.atArrival[1] : (r.h.simdi.orta_dk ?? 1e9));
    return [...rows].sort((a, b) => (a.h.id === nearestId ? -1 : b.h.id === nearestId ? 1 : key(a) - key(b)));
  }, [rows, nearestId]);

  const recRow = rows.find((r) => r.h.id === rec?.id);
  const anyFictional = data?.hastaneler.some((h) => h.kurgusal);
  const directions = (lat: number, lon: number) =>
    Linking.openURL(`https://www.google.com/maps/dir/?api=1&destination=${lat},${lon}&travelmode=${mode === 'araba' ? 'driving' : 'walking'}`);

  return (
    <ScrollView contentContainerStyle={st.wrap}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={async () => { setRefreshing(true); await load(); setRefreshing(false); }} />}>
      <EmergencyStrip />

      {anyFictional && (
        <Note tone="warn">Karşılaştırma demosu: hastaneler ve konumları kurgusaldır, süreler sentetik veriye dayanır.</Note>
      )}

      <Card>
        <H2>Nereden gideceksiniz?</H2>
        <View style={st.seg}>
          <Seg on={where.kind === 'gps'} label="Konumum" onPress={useGps} />
          <Seg on={where.kind === 'demo'} label="Demo konum" onPress={() => data?.demo_konum && setWhere({ kind: 'demo', ...data.demo_konum, label: data.demo_konum.ad })} />
          <Seg on={where.kind === 'none'} label="Konumsuz" onPress={() => setWhere({ kind: 'none' })} />
        </View>
        {where.kind !== 'none' && (
          <View style={st.seg}>
            <Seg on={mode === 'araba'} label="Araba" onPress={() => setMode('araba')} />
            <Seg on={mode === 'yuruyus'} label="Yürüyerek" onPress={() => setMode('yuruyus')} />
          </View>
        )}
        <P muted>
          {where.kind === 'none'
            ? 'Konum olmadan yol süresi hesaplanamaz; hastaneler yalnızca şu anki beklemeye göre listelenir.'
            : `${where.label}. Konumunuz telefondan çıkmaz; yol süresi telefonda hesaplanır.`}
        </P>
        {locMsg && <P>{locMsg}</P>}
      </Card>

      {error && <Note tone="warn">{error}</Note>}

      {rec && recRow && recRow.atArrival && (
        <View style={st.rec}>
          <Text style={st.recTop}>Önerilen</Text>
          <Text style={st.recName}>{recRow.h.ad}{recRow.h.kurgusal ? ' (kurgusal)' : ''}</Text>
          <Text style={st.recLine}>
            {fmtDuration(recRow.travel!)} yol · varış ~{clockAfter(recRow.travel!)} · varışta bekleme {fmtRange(recRow.atArrival[0], recRow.atArrival[2])}
          </Text>
          <Text style={st.recReason}>{rec.reason}</Text>
          <Pressable onPress={() => directions(recRow.h.lat, recRow.h.lon)} style={st.recBtn} accessibilityRole="button">
            <Text style={st.recBtnText}>Yol tarifi</Text>
          </Pressable>
        </View>
      )}

      {where.kind !== 'none' && (
        <Note>
          Yolda yoğunluk değişebilir. Tahmin şu anki kuyruktan değil, <Text style={{ fontWeight: '700' }}>varış saatinizdeki</Text> beklenen
          durumdan yapılır ve her dakika yenilenir. Yol uzadıkça aralık genişler.
        </Note>
      )}

      {sorted.map(({ h, travel, atArrival }) => {
        const long = travel !== null && travel > MAX_TRAVEL_MIN;
        return (
          <Card key={h.id} style={h.id === rec?.id ? { borderColor: color.accent, borderWidth: 2 } : undefined}>
            <View style={st.rowHead}>
              <Text style={st.hName}>{h.ad}</Text>
              {h.id === nearestId && <Tag text="En yakın" />}
              {h.kurgusal && <Tag text="kurgusal" muted />}
            </View>
            {where.kind !== 'none' && (
              travel === null
                ? <P muted>Yürüme mesafesinde değil (5 km’den uzun).</P>
                : <Text style={st.big}>{fmtDuration(travel)} yol · varış ~{clockAfter(travel)}</Text>
            )}
            {atArrival && <P>Varışınızda tahmini bekleme: <Text style={st.strong}>{fmtRange(atArrival[0], atArrival[2])}</Text></P>}
            {atArrival && travel !== null && <P>Toplam (yol + bekleme): <Text style={st.strong}>~{fmtDuration(travel + atArrival[1])}</Text></P>}
            <P muted>Şu an: {h.simdi.metin}{h.simdi.bekleyen !== null ? ` · sırada ${h.simdi.bekleyen} hasta` : ''}</P>
            {long && <Note tone="warn">Uzun yol. Acil bir durumda en yakın hastaneye gidin ya da 112’yi arayın.</Note>}
            {travel !== null && <Button title="Yol tarifi" kind="ghost" onPress={() => directions(h.lat, h.lon)} />}
          </Card>
        );
      })}

      <Card>
        <H2>Öneri nasıl yapılıyor?</H2>
        <Bullet>Her hastane için varış saatinizdeki bekleme tahmin edilir: şu anki kuyruktan başlanır, yol süresi boyunca gelecek hastalar geçmişteki saatlik yoğunluktan, görevdeki hekim sayısı çizelgeden alınır.</Bullet>
        <Bullet>Toplam süre = yol + varıştaki bekleme.</Bullet>
        <Bullet>En yakın hastane temel alınır. Başka bir hastane ancak toplam süreyi en az {MIN_SAVING_MIN} dk kısaltıyorsa, bu kazanç tahmin belirsizliğinden büyükse ve yol {MAX_TRAVEL_MIN} dk’yı geçmiyorsa önerilir.</Bullet>
        <Bullet>Yol süreleri yaklaşıktır (kuş uçuşu mesafe, ortalama hız; trafik dahil değil). Kesin rota için “Yol tarifi”ni kullanın.</Bullet>
      </Card>
    </ScrollView>
  );
}

function Seg({ on, label, onPress }: { on: boolean; label: string; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} style={[st.segBtn, on && st.segOn]} accessibilityRole="button" accessibilityState={{ selected: on }}>
      <Text style={[st.segText, on && { color: '#fff' }]}>{label}</Text>
    </Pressable>
  );
}

function Tag({ text, muted }: { text: string; muted?: boolean }) {
  return <Text style={[st.tag, muted && st.tagMuted]}>{text}</Text>;
}

const st = StyleSheet.create({
  wrap: { padding: space.l, gap: space.m, paddingBottom: space.xxl },
  seg: { flexDirection: 'row', gap: 6 },
  segBtn: { flex: 1, paddingVertical: 10, alignItems: 'center', borderRadius: radius.s, borderWidth: 1, borderColor: color.line, backgroundColor: '#fff' },
  segOn: { backgroundColor: color.accent, borderColor: color.accent },
  segText: { fontWeight: '700', color: color.ink, fontSize: 14 },
  rec: { backgroundColor: color.accent, borderRadius: radius.l, padding: space.xl, gap: 6 },
  recTop: { color: '#fff', opacity: 0.85, fontSize: 12, letterSpacing: 1.6, textTransform: 'uppercase', fontWeight: '600' },
  recName: { color: '#fff', fontSize: 24, fontWeight: '800' },
  recLine: { color: '#fff', fontSize: 15.5, lineHeight: 22 },
  recReason: { color: '#fff', opacity: 0.9, fontSize: 14, lineHeight: 20 },
  recBtn: { backgroundColor: '#fff', borderRadius: radius.m, paddingVertical: 12, alignItems: 'center', marginTop: space.s },
  recBtnText: { color: color.accent, fontWeight: '800', fontSize: 16 },
  rowHead: { flexDirection: 'row', alignItems: 'center', gap: space.s, flexWrap: 'wrap' },
  hName: { fontSize: 17, fontWeight: '700', color: color.ink },
  tag: { fontSize: 11.5, fontWeight: '700', color: color.accent, backgroundColor: color.accentSoft, paddingHorizontal: 8, paddingVertical: 2, borderRadius: 999, overflow: 'hidden' },
  tagMuted: { color: color.ink2, backgroundColor: '#eef0ee' },
  big: { fontSize: 16, fontWeight: '700', color: color.ink },
  strong: { fontWeight: '700', color: color.ink },
});
