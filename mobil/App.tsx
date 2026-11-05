import AsyncStorage from '@react-native-async-storage/async-storage';
import { StatusBar } from 'expo-status-bar';
import React, { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaProvider, useSafeAreaInsets } from 'react-native-safe-area-context';

import { api, Status } from './src/api';
import { useWaitWatcher } from './src/notify';
import CompareScreen from './src/screens/CompareScreen';
import HospitalScreen from './src/screens/HospitalScreen';
import NotifyScreen from './src/screens/NotifyScreen';
import NowScreen from './src/screens/NowScreen';
import PrivacyScreen from './src/screens/PrivacyScreen';
import WhenScreen from './src/screens/WhenScreen';
import { color, space } from './src/theme';

type Tab = 'now' | 'compare' | 'when' | 'notify' | 'hospital';
const TABS: { id: Tab; label: string }[] = [
  { id: 'now', label: 'Şimdi' },
  { id: 'compare', label: 'Karşılaştır' },
  { id: 'when', label: 'Ne zaman' },
  { id: 'notify', label: 'Bildirim' },
  { id: 'hospital', label: 'Hastane' },
];
const SEEN_KEY = 'bilgilendirme_okundu_v1';

function Shell() {
  const insets = useSafeAreaInsets();
  const [tab, setTab] = useState<Tab>('now');
  const [status, setStatus] = useState<Status | null>(null);
  const [seen, setSeen] = useState<boolean | null>(null);
  const [privacy, setPrivacy] = useState(false);
  const watcher = useWaitWatcher();

  useEffect(() => {
    AsyncStorage.getItem(SEEN_KEY).then((v) => setSeen(v === '1')).catch(() => setSeen(false));
    const load = () => api.status().then(setStatus).catch(() => {});
    load();
    const id = setInterval(load, 60000);
    return () => clearInterval(id);
  }, []);

  const acceptIntro = () => {
    setSeen(true);
    AsyncStorage.setItem(SEEN_KEY, '1').catch(() => {});
  };

  if (seen === null) return <View style={[st.root, { paddingTop: insets.top }]} />;
  if (!seen || privacy) {
    return (
      <View style={[st.root, { paddingTop: insets.top, paddingBottom: insets.bottom }]}>
        <PrivacyScreen first={!seen} onClose={() => (seen ? setPrivacy(false) : acceptIntro())} />
      </View>
    );
  }

  return (
    <View style={[st.root, { paddingTop: insets.top }]}>
      <View style={st.header}>
        <View style={st.mark}><Text style={st.markPlus}>+</Text></View>
        <View style={{ flex: 1 }}>
          <Text style={st.appName}>Yeşil Alan</Text>
          <Text style={st.appSub}>Acil servis bekleme tahmini</Text>
        </View>
        {watcher.state.active && <Text style={st.watching}>Takipte</Text>}
      </View>

      <View style={{ flex: 1 }}>
        {tab === 'now' && <NowScreen status={status} />}
        {tab === 'compare' && <CompareScreen />}
        {tab === 'when' && <WhenScreen status={status} />}
        {tab === 'notify' && <NotifyScreen watcher={watcher} />}
        {tab === 'hospital' && <HospitalScreen onPrivacy={() => setPrivacy(true)} />}
      </View>

      <View style={[st.tabbar, { paddingBottom: Math.max(insets.bottom, space.s) }]} accessibilityRole="tablist">
        {TABS.map((t) => {
          const on = t.id === tab;
          return (
            <Pressable key={t.id} onPress={() => setTab(t.id)} style={st.tab}
              accessibilityRole="tab" accessibilityState={{ selected: on }}>
              <View style={[st.tabPip, on && st.tabPipOn]} />
              <Text style={[st.tabText, on && st.tabTextOn]}>{t.label}</Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

export default function App() {
  return (
    <SafeAreaProvider>
      <StatusBar style="dark" />
      <Shell />
    </SafeAreaProvider>
  );
}

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: color.bg },
  header: { flexDirection: 'row', alignItems: 'center', gap: space.m, paddingHorizontal: space.l, paddingVertical: space.m, borderBottomWidth: 1, borderBottomColor: color.line, backgroundColor: color.card },
  mark: { width: 34, height: 34, borderRadius: 9, backgroundColor: color.accent, alignItems: 'center', justifyContent: 'center' },
  markPlus: { color: '#fff', fontSize: 24, fontWeight: '800', marginTop: -2 },
  appName: { fontSize: 18, fontWeight: '800', color: color.ink },
  appSub: { fontSize: 12.5, color: color.muted },
  watching: { fontSize: 12, fontWeight: '700', color: color.accent, backgroundColor: color.accentSoft, paddingHorizontal: 10, paddingVertical: 4, borderRadius: 999, overflow: 'hidden' },
  tabbar: { flexDirection: 'row', borderTopWidth: 1, borderTopColor: color.line, backgroundColor: color.card, paddingTop: 6 },
  tab: { flex: 1, alignItems: 'center', gap: 5, paddingVertical: 4 },
  tabPip: { width: 28, height: 4, borderRadius: 2, backgroundColor: 'transparent' },
  tabPipOn: { backgroundColor: color.accent },
  tabText: { fontSize: 12.5, fontWeight: '600', color: color.muted },
  tabTextOn: { color: color.ink, fontWeight: '800' },
});
