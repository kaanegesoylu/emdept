import React from 'react';
import { Linking, Pressable, StyleSheet, Text, View, ViewStyle } from 'react-native';

import type { Prediction, Status } from './api';
import { color, level, radius, space } from './theme';

/** Her ekranın üstünde: hayati tehlikede 112. Hiçbir tahmin bunun önüne geçmez. */
export function EmergencyStrip() {
  return (
    <Pressable
      onPress={() => Linking.openURL('tel:112')}
      style={({ pressed }) => [s.emg, pressed && { opacity: 0.85 }]}
      accessibilityRole="button"
      accessibilityLabel="Hayati tehlike varsa 112'yi arayın"
    >
      <Text style={s.emgText}>
        Hayati tehlike varsa beklemeyin: <Text style={s.emgBold}>112’yi arayın</Text>
      </Text>
      <View style={s.emgBtn}>
        <Text style={s.emgBtnText}>Ara</Text>
      </View>
    </Pressable>
  );
}

/** Verinin ne olduğu her zaman görünür: sentetik veri gerçek hastane gibi sunulmaz. */
export function SourceNote({ status, live }: { status: Status | null; live?: boolean }) {
  if (!status) return null;
  const synthetic = status.veri.kind === 'synthetic';
  const parts = [
    live ? 'Canlı akış: simülasyon (hastane sistemine anlık erişim varsayımı)' : `Dayanak: son ${status.gecmis_hafta} haftanın kayıtları`,
    synthetic ? 'Sentetik örnek veri — gerçek hastaneye ait değildir' : status.veri.label,
  ];
  return (
    <View style={[s.source, synthetic && s.sourceWarn]}>
      <Text style={s.sourceText}>{parts.join(' · ')}</Text>
    </View>
  );
}

export function LevelChip({ value }: { value: Prediction['duzey'] }) {
  const l = level[value] ?? level.sakin;
  return (
    <View style={s.chip} accessibilityLabel={`Yoğunluk: ${l.label}`}>
      <Text style={[s.chipIcon, { color: l.color }]}>{l.icon}</Text>
      <Text style={s.chipText}>{l.label}</Text>
    </View>
  );
}

export function Card({ children, style }: { children: React.ReactNode; style?: ViewStyle }) {
  return <View style={[s.card, style]}>{children}</View>;
}

export function Note({ children, tone = 'info' }: { children: React.ReactNode; tone?: 'info' | 'warn' }) {
  return (
    <View style={[s.note, tone === 'warn' && s.noteWarn]}>
      <Text style={s.noteText}>{children}</Text>
    </View>
  );
}

export function H2({ children }: { children: React.ReactNode }) {
  return <Text style={s.h2} accessibilityRole="header">{children}</Text>;
}

export function P({ children, muted }: { children: React.ReactNode; muted?: boolean }) {
  return <Text style={[s.p, muted && { color: color.muted }]}>{children}</Text>;
}

export function Bullet({ children }: { children: React.ReactNode }) {
  return (
    <View style={s.bulletRow}>
      <Text style={s.bulletDot}>•</Text>
      <Text style={[s.p, { flex: 1 }]}>{children}</Text>
    </View>
  );
}

export function Button({ title, onPress, kind = 'primary', disabled }: { title: string; onPress: () => void; kind?: 'primary' | 'ghost'; disabled?: boolean }) {
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      accessibilityRole="button"
      style={({ pressed }) => [s.btn, kind === 'ghost' && s.btnGhost, (pressed || disabled) && { opacity: 0.6 }]}
    >
      <Text style={[s.btnText, kind === 'ghost' && { color: color.accent }]}>{title}</Text>
    </Pressable>
  );
}

export function timeAgo(iso?: string): string {
  if (!iso) return '';
  const d = new Date(iso);
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

const s = StyleSheet.create({
  emg: { flexDirection: 'row', alignItems: 'center', gap: space.m, backgroundColor: color.critSoft, borderColor: '#f3c3c3', borderWidth: 1, borderRadius: radius.m, paddingVertical: space.s, paddingHorizontal: space.m },
  emgText: { flex: 1, color: color.ink, fontSize: 14, lineHeight: 19 },
  emgBold: { fontWeight: '700', color: color.crit },
  emgBtn: { backgroundColor: color.crit, borderRadius: 999, paddingHorizontal: space.l, paddingVertical: 6 },
  emgBtnText: { color: '#fff', fontWeight: '700' },
  source: { borderRadius: radius.s, paddingVertical: 6, paddingHorizontal: space.m, backgroundColor: color.accentSoft },
  sourceWarn: { backgroundColor: color.noteBg },
  sourceText: { fontSize: 12.5, color: color.ink2, lineHeight: 17 },
  chip: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#fff', borderRadius: 999, paddingVertical: 5, paddingHorizontal: 12, alignSelf: 'flex-start' },
  chipIcon: { fontSize: 14, fontWeight: '700' },
  chipText: { fontSize: 15, fontWeight: '700', color: color.ink },
  card: { backgroundColor: color.card, borderRadius: radius.m, padding: space.l, borderWidth: 1, borderColor: color.line, gap: space.s },
  note: { backgroundColor: color.accentSoft, borderRadius: radius.m, padding: space.m },
  noteWarn: { backgroundColor: color.noteBg, borderWidth: 1, borderColor: color.noteLine },
  noteText: { color: color.ink, fontSize: 14.5, lineHeight: 20 },
  h2: { fontSize: 18, fontWeight: '700', color: color.ink },
  p: { fontSize: 15, lineHeight: 21, color: color.ink2 },
  bulletRow: { flexDirection: 'row', gap: space.s },
  bulletDot: { fontSize: 15, lineHeight: 21, color: color.ink2 },
  btn: { backgroundColor: color.accent, borderRadius: radius.m, paddingVertical: 13, alignItems: 'center' },
  btnGhost: { backgroundColor: 'transparent', borderWidth: 1, borderColor: color.accent },
  btnText: { color: color.onAccent, fontWeight: '700', fontSize: 16 },
});
