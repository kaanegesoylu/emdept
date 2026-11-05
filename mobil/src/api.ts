// Tahmin API'si istemcisi. Uygulama hiçbir kişisel veri göndermez: istekler yalnızca gün/saat içerir.
import AsyncStorage from '@react-native-async-storage/async-storage';
import Constants from 'expo-constants';
import { Platform } from 'react-native';

export type Level = 'sakin' | 'yogun' | 'cok_yogun';

export type Prediction = {
  alt_dk: number | null;
  orta_dk: number | null;
  ust_dk: number | null;
  metin: string;
  yontem: 'live' | 'history_observed' | 'history_model' | 'no_doctor' | 'unavailable';
  dayanak: string;
  duzey: Level;
  bekleyen: number | null;
  hekim: number | null;
  saat?: string;
};

export type Status = {
  veri: { kind: 'synthetic' | 'real'; label: string; file?: string };
  canli_akis: { tur: string; aciklama: string; hiz: number };
  aralik: string;
  gecmis_hafta: number;
  zaman: string;
};

export type Cell = { gun: number; saat: number; alt_dk: number | null; orta_dk: number | null; ust_dk: number | null; yontem: string };

export type Hospital = {
  ad: string;
  birim: string;
  adres: string;
  harita_sorgu: string;
  santral_telefon: string;
  calisma_saatleri: string;
};

export type HospitalLive = {
  id: string;
  ad: string;
  kurgusal: boolean;
  ana: boolean;
  lat: number;
  lon: number;
  veri: 'synthetic' | 'real';
  simdi: Prediction;
  varis_egrisi: { dakika: number; alt: number | null; orta: number | null; ust: number | null }[];
};

export type HospitalsResponse = {
  hastaneler: HospitalLive[];
  demo_konum: { ad: string; lat: number; lon: number } | null;
  zaman: string;
  kural: string;
};

const KEY = 'api_adresi';

/** Geliştirme sırasında Expo sunucusunun çalıştığı bilgisayarı bulur; API aynı bilgisayarda 8000 portundadır. */
export function defaultBaseUrl(): string {
  if (Platform.OS === 'web' && typeof window !== 'undefined') {
    return `http://${window.location.hostname}:8000`;
  }
  const hostUri = Constants.expoConfig?.hostUri ?? '';
  const host = hostUri.split(':')[0];
  return host ? `http://${host}:8000` : 'http://localhost:8000';
}

let cached: string | null = null;

export async function getBaseUrl(): Promise<string> {
  if (cached) return cached;
  let url = defaultBaseUrl();
  try {
    url = (await AsyncStorage.getItem(KEY)) || url;
  } catch {
    // Okunamazsa varsayılan adres kullanılır.
  }
  cached = url;
  return url;
}

export async function setBaseUrl(url: string): Promise<void> {
  cached = url.trim().replace(/\/$/, '') || null;
  try {
    if (cached) await AsyncStorage.setItem(KEY, cached);
    else await AsyncStorage.removeItem(KEY);
  } catch {
    // Kaydedilemezse yalnızca bu oturumda geçerli olur.
  }
}

async function get<T>(path: string): Promise<T> {
  const base = await getBaseUrl();
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 8000);
  try {
    const res = await fetch(base + path, { signal: ctrl.signal });
    if (!res.ok) throw new Error(`Sunucu ${res.status} döndü`);
    return (await res.json()) as T;
  } finally {
    clearTimeout(timer);
  }
}

export const api = {
  status: () => get<Status>('/api/durum'),
  live: () => get<Prediction>('/api/tahmin/canli'),
  history: (gun: number, saat: number) => get<Prediction>(`/api/tahmin/gecmis?gun=${gun}&saat=${saat}`),
  week: () => get<{ hucreler: Cell[]; veri: string }>('/api/tahmin/haftalik'),
  hospital: () => get<Hospital>('/api/hastane'),
  hospitals: () => get<HospitalsResponse>('/api/hastaneler'),
};

/** Pazartesi = 0 olacak şekilde bugünün günü. */
export function todayIndex(d = new Date()): number {
  return (d.getDay() + 6) % 7;
}
