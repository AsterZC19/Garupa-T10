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
