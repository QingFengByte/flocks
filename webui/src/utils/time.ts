/**
 * Shared time formatting utilities.
 *
 * All "smart time" display logic should use these helpers to avoid
 * duplicate implementations across components.
 */

export function formatSmartTime(timestamp: number): string {
  const d = new Date(timestamp);
  return `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()} ${formatTime12h(d)}`;
}

export function formatSessionDate(ts: number): string {
  if (!ts) return '';
  const d = new Date(ts);
  return `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()} ${formatTime12h(d)}`;
}

function formatTime12h(d: Date): string {
  let hours = d.getHours();
  const minutes = d.getMinutes().toString().padStart(2, '0');
  const ampm = hours >= 12 ? 'PM' : 'AM';
  hours = hours % 12;
  if (hours === 0) hours = 12;
  return `${hours}:${minutes} ${ampm}`;
}
