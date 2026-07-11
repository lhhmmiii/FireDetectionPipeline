export function formatMs(value: number | null | undefined): string {
  if (value === null || value === undefined) return '--';
  if (value < 10) return `${value.toFixed(1)} ms`;
  return `${Math.round(value)} ms`;
}

export function formatFps(value: number | null | undefined): string {
  if (value === null || value === undefined) return '--';
  return `${value.toFixed(1)} fps`;
}

export function formatPct(value: number | null | undefined): string {
  if (value === null || value === undefined) return '--';
  return `${(value * 100).toFixed(1)}%`;
}
