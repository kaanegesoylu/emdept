// Sakin, klinik bir palet: yeşil alanın rengi vurgu, durumlar renk + simge + yazı ile.
export const color = {
  bg: '#f3f6f4',
  card: '#ffffff',
  ink: '#14201c',
  ink2: '#4a5650',
  muted: '#7c8580',
  line: '#dde3de',
  accent: '#0e6a55',
  accentSoft: '#dcece5',
  onAccent: '#ffffff',
  good: '#0b8a0b',
  warn: '#a86f00',
  crit: '#c22f2f',
  critSoft: '#fdecec',
  noteBg: '#fff7e0',
  noteLine: '#f1d58a',
  noteInk: '#3d2f00',
};

export const space = { xs: 4, s: 8, m: 12, l: 16, xl: 24, xxl: 32 };
export const radius = { s: 8, m: 14, l: 20 };

export const level = {
  sakin: { label: 'Sakin', icon: '●', color: color.good },
  yogun: { label: 'Yoğun', icon: '▲', color: color.warn },
  cok_yogun: { label: 'Çok yoğun', icon: '■', color: color.crit },
} as const;

export const DAYS = ['Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt', 'Paz'];
export const DAYS_LONG = ['Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi', 'Pazar'];
