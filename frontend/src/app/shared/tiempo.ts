/** Utilidades de fecha/duración compartidas. */

export function fecha(ts?: string | null): string {
  if (!ts) return '—';
  return new Date(ts).toLocaleString();
}

export function hace(ts?: string | null): string {
  if (!ts) return '—';
  const seg = Math.floor((Date.now() - new Date(ts).getTime()) / 1000);
  if (seg < 60) return `${seg}s`;
  if (seg < 3600) return `${Math.floor(seg / 60)}m`;
  if (seg < 86400) return `${Math.floor(seg / 3600)}h`;
  return `${Math.floor(seg / 86400)}d`;
}

/** Duración legible entre dos instantes (o hasta ahora si fin es nulo). */
export function duracion(inicio: string, fin?: string | null): string {
  const a = new Date(inicio).getTime();
  const b = fin ? new Date(fin).getTime() : Date.now();
  let seg = Math.max(0, Math.floor((b - a) / 1000));
  const d = Math.floor(seg / 86400); seg -= d * 86400;
  const h = Math.floor(seg / 3600); seg -= h * 3600;
  const m = Math.floor(seg / 60);
  const partes = [];
  if (d) partes.push(`${d}d`);
  if (h) partes.push(`${h}h`);
  if (m || (!d && !h)) partes.push(`${m}m`);
  return partes.join(' ');
}
