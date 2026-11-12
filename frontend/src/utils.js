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

// 热力图配色：5 档低饱和莫兰迪雾霾蓝渐变，intensity 0→1（浅→深），温润护眼
const HEAT_STOPS_LIGHT = [
  [0.0, 236, 240, 246], // #ECF0F6 极淡灰蓝
  [0.2, 216, 224, 236], // #D8E0EC
  [0.45, 174, 191, 214], // #AEBFD6
  [0.7, 122, 148, 181], //  #7A94B5
  [1.0, 77, 104, 140], //   #4D688C 柔和钢青蓝
];

// 深色模式：柔和石板灰蓝空格 + 低饱和雾蓝渐变，不刺眼
const HEAT_STOPS_DARK = [
  [0.0, 45, 51, 64],    // #2D3340 柔和低对比空格
  [0.2, 56, 68, 89],    // #384459
  [0.45, 73, 93, 124],  // #495D7C
  [0.7, 96, 123, 161],  // #607BA1
  [1.0, 126, 156, 196], // #7E9CC4 柔和雾霾蓝
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
    fg: intensity > 0.55 ? '#F5F7FC' : dark ? '#CBD2E1' : '#49454F',
  };
}
