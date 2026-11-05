// Hastane karşılaştırma ve öneri kuralı — telefonda çalışır, konum telefondan çıkmaz.
// Python eşi ve testleri: acil/routing.py, tests/test_routing.py (aynı sabitler).

export type Mode = 'araba' | 'yuruyus';
export type CurvePoint = { dakika: number; alt: number | null; orta: number | null; ust: number | null };

export const MIN_SAVING_MIN = 15;
export const MAX_TRAVEL_MIN = 60;
const DETOUR: Record<Mode, number> = { araba: 1.3, yuruyus: 1.25 };
const WALK_KMH = 4.5;
const WALK_MAX_KM = 5;

export function haversineKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371, rad = (x: number) => (x * Math.PI) / 180;
  const dp = rad(lat2 - lat1), dl = rad(lon2 - lon1);
  const a = Math.sin(dp / 2) ** 2 + Math.cos(rad(lat1)) * Math.cos(rad(lat2)) * Math.sin(dl / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

/** Yaklaşık yol süresi (dk), trafik hariç. Yürüyüş 5 km'yi aşarsa null. */
export function travelMinutes(kmStraight: number, mode: Mode): number | null {
  const road = kmStraight * DETOUR[mode];
  if (mode === 'yuruyus') return road > WALK_MAX_KM ? null : (road / WALK_KMH) * 60;
  const city = Math.min(road, 10);
  return (city / 30 + Math.max(0, road - 10) / 70) * 60;
}

/** Varış eğrisinden τ dakika için (alt, orta, üst). */
export function interp(curve: CurvePoint[], minutes: number): [number, number, number] | null {
  const pts = curve.filter((c) => c.orta !== null) as { dakika: number; alt: number; orta: number; ust: number }[];
  if (!pts.length) return null;
  const last = pts[pts.length - 1];
  if (minutes >= last.dakika) return [last.alt, last.orta, last.ust];
  for (let i = 0; i < pts.length - 1; i++) {
    const a = pts[i], b = pts[i + 1];
    if (a.dakika <= minutes && minutes <= b.dakika) {
      const f = (minutes - a.dakika) / (b.dakika - a.dakika);
      return [a.alt + f * (b.alt - a.alt), a.orta + f * (b.orta - a.orta), a.ust + f * (b.ust - a.ust)];
    }
  }
  return [pts[0].alt, pts[0].orta, pts[0].ust];
}

export type Option = { id: string; travel: number; lo: number; mid: number; hi: number };
const total = (o: Option) => o.travel + o.mid;
const spread = (o: Option) => (o.hi - o.lo) / 2;

/** Öneri kuralı: en yakın hastane temeldir; başka hastane ancak anlamlı ve belirsizlikten büyük bir kazançla önerilir. */
export function recommend(options: Option[]): { id: string; reason: string } {
  if (!options.length) return { id: '', reason: '' };
  const nearest = options.reduce((a, b) => (b.travel < a.travel ? b : a));
  for (const o of [...options].sort((a, b) => total(a) - total(b))) {
    if (o === nearest) continue;
    const saving = total(nearest) - total(o);
    if (o.travel <= MAX_TRAVEL_MIN && saving >= MIN_SAVING_MIN && saving > spread(nearest) + spread(o)) {
      return { id: o.id, reason: `Toplam süre yaklaşık ${Math.round(saving)} dk daha kısa ve bu fark tahmin belirsizliğinden büyük.` };
    }
  }
  return { id: nearest.id, reason: 'En yakın hastane. Başka bir hastane belirgin bir kazanç sağlamıyor.' };
}

export function fmtRange(lo: number, hi: number, step = 5): string {
  const l = Math.floor(lo / step) * step;
  let h = Math.ceil(hi / step) * step;
  if (h <= step) return `${step} dk’dan az`;
  if (l === h) h = l + step;
  return `${l}–${h} dk`;
}

export function fmtDuration(min: number): string {
  if (min < 60) return `${Math.max(1, Math.round(min))} dk`;
  const h = Math.floor(min / 60), m = Math.round(min % 60);
  return m ? `${h} sa ${m} dk` : `${h} sa`;
}

export function clockAfter(min: number, from = new Date()): string {
  const d = new Date(from.getTime() + min * 60000);
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}
