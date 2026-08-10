// frontend/src/utils.js
export function formatTs(ms, format = 'full') {
  if (!ms) return '-';
  const date = new Date(ms);

  if (format === 'time') {
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');
    return `${hours}:${minutes}`;
  }

  // Default to full date-time string
  return date.toLocaleString('zh-CN');
}

// 热力图配色：5 档蓝色渐变线性插值，intensity 0→1（浅→深），与整体淡蓝主题呼应
const HEAT_STOPS_LIGHT = [
  [0.0, 233, 240, 255], // #E9F0FF 近白淡蓝
  [0.2, 214, 228, 252], // #D6E4FC
  [0.45, 163, 193, 244], // #A3C1F4
  [0.7, 96, 143, 219], //   #608FDB
  [1.0, 42, 89, 158], //    #2A599E 深蓝
];

// 深色模式：更暗的空格 + 更亮的深档，保证对比度
const HEAT_STOPS_DARK = [
  [0.0, 26, 31, 45], //     #1A1F2D 近表面
  [0.2, 40, 55, 84], //     #283754
  [0.45, 62, 88, 134], //   #3E5886
  [0.7, 94, 132, 197], //   #5E84C5
  [1.0, 145, 178, 244], //  #91B2F4 亮蓝
];

export function heatColor(intensity, dark = false) {
  const stops = dark ? HEAT_STOPS_DARK : HEAT_STOPS_LIGHT;
  const t = Math.max(0, Math.min(1, intensity));
  let i = 0;
  while (i < stops.length - 2 && t > stops[i + 1][0]) i++;
  const [t0, r0, g0, b0] = stops[i];
  const [t1, r1, g1, b1] = stops[i + 1];
  const f = t1 === t0 ? 0 : (t - t0) / (t1 - t0);
  const r = Math.round(r0 + (r1 - r0) * f);
  const g = Math.round(g0 + (g1 - g0) * f);
  const b = Math.round(b0 + (b1 - b0) * f);
  return {
    bg: `rgb(${r}, ${g}, ${b})`,
    fg: intensity > 0.55 ? '#FFFFFF' : dark ? '#CAC4D0' : '#49454F',
  };
}
