import { Component, OnDestroy, OnInit, computed, inject, signal } from '@angular/core';
import { FlujoOverview } from '../../core/models';
import { RecursosService } from '../../core/recursos.service';

type Rango = '1h' | '6h' | '24h' | '7d';

interface Seg { path: string; color: string; label: string; value: number; pct: number; }
interface Area { path: string; color: string; app: string; }
interface FlowNode { x: number; y: number; ip: string; }
interface FlowArc { path: string; color: string; w: number; label: string; }

const PALETA = ['#3b82f6', '#10b981', '#06b6d4', '#f59e0b', '#8b5cf6', '#94a3b8'];
const PROTO_COLOR: Record<string, string> = { TCP: '#3b82f6', UDP: '#06b6d4', ICMP: '#f59e0b', Otros: '#94a3b8' };
// Paleta cálida/brillante para los arcos del mapa de flujo (estilo imagen).
const FLOW_PALETA = ['#22d3ee', '#f59e0b', '#34d399', '#a78bfa', '#60a5fa', '#f472b6'];

@Component({
  selector: 'app-flujos',
  standalone: true,
  imports: [],
  templateUrl: './flujos.html',
  styleUrl: './flujos.scss',
})
export class Flujos implements OnInit, OnDestroy {
  private svc = inject(RecursosService);

  d = signal<FlujoOverview | null>(null);
  cargando = signal(true);
  rango = signal<Rango>('7d');
  rangos: Rango[] = ['1h', '6h', '24h', '7d'];
  private timer?: ReturnType<typeof setInterval>;

  ngOnInit(): void { this.cargar(); this.timer = setInterval(() => this.cargar(), 30000); }
  ngOnDestroy(): void { if (this.timer) clearInterval(this.timer); }

  cambiar(r: Rango): void { this.rango.set(r); this.cargar(); }
  refrescar(): void { this.cargar(); }

  cargar(): void {
    this.svc.flujosOverview(this.rango()).subscribe({
      next: (d) => { this.d.set(d); this.cargando.set(false); },
      error: () => this.cargando.set(false),
    });
  }

  // ── Formato ─────────────────────────────────────────────────────────
  fmtBytes(b: number): string {
    if (!b) return '0 B';
    const u = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']; let v = b, i = 0;
    while (v >= 1024 && i < u.length - 1) { v /= 1024; i++; }
    return `${v.toFixed(v >= 100 || i === 0 ? 0 : 1)} ${u[i]}`;
  }
  fmtNum(n: number): string {
    if (n >= 1e6) return (n / 1e6).toFixed(1) + ' M';
    if (n >= 1e3) return n.toLocaleString('es-CO');
    return String(n);
  }
  signo(v: number | null): string { return v == null ? '' : (v >= 0 ? '↑ ' : '↓ ') + Math.abs(v) + '%'; }
  claseDelta(v: number | null): string { return v == null ? 'neu' : v >= 0 ? 'pos' : 'neg'; }

  // ── Sparklines (110×34) ─────────────────────────────────────────────
  spark(vals: number[]): string {
    if (!vals?.length) return '';
    const w = 110, h = 30, max = Math.max(1, ...vals), n = vals.length;
    return vals.map((v, i) =>
      `${(n === 1 ? w / 2 : (i / (n - 1)) * w).toFixed(1)},${(h - (v / max) * h + 2).toFixed(1)}`).join(' ');
  }
  sparkArea(vals: number[]): string {
    const pts = this.spark(vals);
    if (!pts) return '';
    return `0,34 ${pts} 110,34 Z`;
  }

  // ── Dona genérica ───────────────────────────────────────────────────
  private dona(items: { label: string; value: number; color: string }[]): Seg[] {
    const total = items.reduce((s, x) => s + x.value, 0) || 1;
    const cx = 70, cy = 70, r = 58, ir = 38;
    let a = -Math.PI / 2;
    return items.map((it) => {
      const frac = it.value / total;
      const a2 = a + frac * 2 * Math.PI;
      const large = a2 - a > Math.PI ? 1 : 0;
      const p = (ang: number, rad: number) => `${(cx + rad * Math.cos(ang)).toFixed(2)},${(cy + rad * Math.sin(ang)).toFixed(2)}`;
      const path = `M${p(a, r)} A${r},${r} 0 ${large} 1 ${p(a2, r)} L${p(a2, ir)} A${ir},${ir} 0 ${large} 0 ${p(a, ir)} Z`;
      const seg = { path, color: it.color, label: it.label, value: it.value, pct: Math.round(frac * 100) };
      a = a2;
      return seg;
    });
  }

  appsDona = computed<Seg[]>(() =>
    this.dona((this.d()?.apps ?? []).map((x, i) => ({ label: x.app || 'otros', value: x.bytes, color: PALETA[i % PALETA.length] }))),
  );
  protoDona = computed<Seg[]>(() =>
    this.dona((this.d()?.protocolos ?? []).map((x) => ({ label: x.proto, value: x.bytes, color: PROTO_COLOR[x.proto] || '#94a3b8' }))),
  );
  totalApps = computed(() => (this.d()?.apps ?? []).reduce((s, x) => s + x.bytes, 0));
  totalProto = computed(() => (this.d()?.protocolos ?? []).reduce((s, x) => s + x.bytes, 0));

  // ── Área apilada (Traffic over time) ────────────────────────────────
  readonly AW = 640; readonly AH = 230;
  areas = computed<Area[]>(() => {
    const s = this.d()?.serie; if (!s || !s.apilada.length) return [];
    const n = s.labels.length; if (n < 2) return [];
    const capas = s.apilada;
    const totalPorBucket = s.labels.map((_, i) => capas.reduce((sum, c) => sum + (c.valores[i] || 0), 0));
    const max = Math.max(1, ...totalPorBucket);
    const x = (i: number) => (i / (n - 1)) * this.AW;
    const y = (v: number) => this.AH - (v / max) * this.AH;
    const acum = new Array(n).fill(0);
    const out: Area[] = [];
    capas.forEach((c, idx) => {
      const bajo = [...acum];
      for (let i = 0; i < n; i++) acum[i] += (c.valores[i] || 0);
      const arriba = acum.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' L');
      const abajo = bajo.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).reverse().join(' L');
      out.push({ path: `M${arriba} L${abajo} Z`, color: PALETA[idx % PALETA.length], app: c.app });
    });
    return out;
  });
  ejeX = computed<{ x: number; t: string }[]>(() => {
    const labels = this.d()?.serie.labels ?? []; const n = labels.length;
    if (n < 2) return [];
    const paso = Math.max(1, Math.floor(n / 6));
    const out: { x: number; t: string }[] = [];
    for (let i = 0; i < n; i += paso) out.push({ x: (i / (n - 1)) * this.AW, t: labels[i] });
    return out;
  });

  // ── Mapa de flujo (arcos origen→destino) ────────────────────────────
  readonly FW = 640; readonly FH = 300;
  flowNodes = computed<{ src: FlowNode[]; dst: FlowNode[] }>(() => {
    const f = this.d()?.flujo ?? [];
    const srcs = [...new Set(f.map((x) => x.src))].slice(0, 8);
    const dsts = [...new Set(f.map((x) => x.dst))].slice(0, 8);
    const col = (arr: string[], xx: number): FlowNode[] =>
      arr.map((ip, i) => ({ ip, x: xx, y: 30 + (i * (this.FH - 60)) / Math.max(1, arr.length - 1) }));
    return { src: col(srcs, 70), dst: col(dsts, this.FW - 70) };
  });
  flowArcs = computed<FlowArc[]>(() => {
    const f = this.d()?.flujo ?? []; const nodes = this.flowNodes();
    const sm = new Map(nodes.src.map((n) => [n.ip, n])); const dm = new Map(nodes.dst.map((n) => [n.ip, n]));
    const max = Math.max(1, ...f.map((x) => x.bytes));
    const apps = [...new Set(f.map((x) => x.app))];
    const out: FlowArc[] = [];
    for (const x of f) {
      const a = sm.get(x.src); const b = dm.get(x.dst); if (!a || !b) continue;
      const mx = (a.x + b.x) / 2;
      out.push({
        path: `M${a.x},${a.y} C${mx},${a.y} ${mx},${b.y} ${b.x},${b.y}`,
        color: FLOW_PALETA[Math.max(0, apps.indexOf(x.app)) % FLOW_PALETA.length],
        w: 1 + (x.bytes / max) * 5,
        label: `${x.src} → ${x.dst} · ${x.app} · ${this.fmtBytes(x.bytes)}`,
      });
    }
    return out;
  });
  topFlujo = computed(() => (this.d()?.flujo ?? []).slice(0, 5));
  colorApp(app: string): string {
    const apps = [...new Set((this.d()?.flujo ?? []).map((x) => x.app))];
    return FLOW_PALETA[Math.max(0, apps.indexOf(app)) % FLOW_PALETA.length];
  }
}
