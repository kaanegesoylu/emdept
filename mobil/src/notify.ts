// Yerel bildirim: "tahmini bekleme X dakikanın altına inince haber ver".
// Sunucuya hiçbir şey gönderilmez; eşik yalnızca bu telefonda tutulur. Push sunucusu yoktur.
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as Notifications from 'expo-notifications';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Platform } from 'react-native';

import { api } from './api';

export const THRESHOLDS = [15, 30, 45, 60];
const POLL_MS = 30000;
const MAX_WATCH_MS = 3 * 60 * 60 * 1000; // 3 saat sonra takip kendiliğinden durur
const KEY = 'bildirim_esik';

export const notificationsSupported = Platform.OS !== 'web';

if (notificationsSupported) {
  Notifications.setNotificationHandler({
    handleNotification: async () => ({
      shouldShowBanner: true,
      shouldShowList: true,
      shouldPlaySound: true,
      shouldSetBadge: false,
    }),
  });
}

async function ensurePermission(): Promise<boolean> {
  if (!notificationsSupported) return false;
  if (Platform.OS === 'android') {
    await Notifications.setNotificationChannelAsync('bekleme', {
      name: 'Bekleme süresi',
      importance: Notifications.AndroidImportance.HIGH,
    });
  }
  const cur = await Notifications.getPermissionsAsync();
  if (cur.granted) return true;
  const req = await Notifications.requestPermissionsAsync({ ios: { allowAlert: true, allowSound: true, allowBadge: false } });
  return req.granted;
}

export type WatchState = {
  active: boolean;
  threshold: number;
  startedAt: number | null;
  lastMid: number | null;
  message: string | null;
};

export function useWaitWatcher() {
  const [state, setState] = useState<WatchState>({ active: false, threshold: 30, startedAt: null, lastMid: null, message: null });
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    AsyncStorage.getItem(KEY).then((v) => v && setState((s) => ({ ...s, threshold: Number(v) || 30 }))).catch(() => {});
    return () => { if (timer.current) clearInterval(timer.current); };
  }, []);

  const stop = useCallback((message: string | null = null) => {
    if (timer.current) clearInterval(timer.current);
    timer.current = null;
    setState((s) => ({ ...s, active: false, startedAt: null, message }));
  }, []);

  const check = useCallback(async (threshold: number, startedAt: number) => {
    if (Date.now() - startedAt > MAX_WATCH_MS) {
      stop('Takip 3 saat sonra kendiliğinden durdu.');
      return;
    }
    try {
      const p = await api.live();
      setState((s) => ({ ...s, lastMid: p.orta_dk }));
      if (p.orta_dk !== null && p.yontem === 'live' && p.orta_dk <= threshold) {
        await Notifications.scheduleNotificationAsync({
          content: {
            title: 'Yeşil alanda bekleme azaldı',
            body: `Tahmini bekleme şu an ${p.metin}. Bu bir tahmindir; durumunuz acilse beklemeden başvurun.`,
          },
          trigger: null,
        });
        stop(`Bildirim gönderildi: tahmini bekleme ${p.metin}.`);
      }
    } catch {
      // Bağlantı yoksa bir sonraki denemede tekrar bakılır.
    }
  }, [stop]);

  const start = useCallback(async () => {
    const ok = await ensurePermission();
    if (!ok) {
      setState((s) => ({ ...s, message: 'Bildirim izni verilmedi. Telefon ayarlarından izin verebilirsiniz.' }));
      return;
    }
    const startedAt = Date.now();
    setState((s) => ({ ...s, active: true, startedAt, message: null }));
    const thr = state.threshold;
    check(thr, startedAt);
    timer.current = setInterval(() => check(thr, startedAt), POLL_MS);
  }, [check, state.threshold]);

  const setThreshold = useCallback((t: number) => {
    setState((s) => ({ ...s, threshold: t }));
    AsyncStorage.setItem(KEY, String(t)).catch(() => {});
  }, []);

  return { state, start, stop: () => stop(null), setThreshold };
}
