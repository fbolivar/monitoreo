import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { RecursosService } from '../../core/recursos.service';
import { TopologiaEnlace, TopologiaNodo } from '../../core/models';
import { Mapa } from '../mapa/mapa';

interface NodoPos extends TopologiaNodo { x: number; y: number; nivel: number; }
interface EnlacePos {
  origen: string; destino: string;
  x1: number; y1: number; x2: number; y2: number;
  pOrigen: string; pDestino: string;       // puertos en cada extremo
  // posiciones de las etiquetas de puerto, cerca de cada nodo
  lox: number; loy: number; ldx: number; ldy: number;
}
interface Banda { y: number; label: string; }
interface SitioOpt { id: number | 'sin'; nombre: string; n: number; }
interface GrafoSede { width: number; height: number; nodos: NodoPos[]; bandas: Banda[]; }

// Geometría.
const NIVEL_H = 132;
const TOP_PAD = 58;
const MIN_W = 820;
const COL_W = 186;
const CARD_W = 156;
const CARD_H = 50;

// Insignia y etiqueta por tipo de recurso.
const TIPO_INFO: Record<string, { abbr: string; label: string }> = {
  firewall:    { abbr: 'FW',  label: 'Firewall' },
  switch_lan:  { abbr: 'SW',  label: 'Switch LAN' },
  switch_san:  { abbr: 'SAN', label: 'Switch SAN' },
  servidor:    { abbr: 'SRV', label: 'Servidor' },
  nas:         { abbr: 'NAS', label: 'NAS' },
  ups:         { abbr: 'UPS', label: 'UPS' },
  starlink:    { abbr: 'STL', label: 'Starlink' },
  enlace_wan:  { abbr: 'WAN', label: 'Enlace WAN' },
  sitio_web:   { abbr: 'WEB', label: 'Sitio web' },
};

@Component({
  selector: 'app-topologia',
  standalone: true,
  imports: [RouterLink, Mapa],
  templateUrl: './topologia.html',
  styleUrl: './topologia.scss',
})
export class Topologia implements OnInit {
  private svc = inject(RecursosService);

  tab = signal<'mapa' | 'componentes'>('mapa');

  nodos = signal<TopologiaNodo[]>([]);
  enlaces = signal<TopologiaEnlace[]>([]);
  cargando = signal(true);
  seleccion = signal<string | null>(null);
  hover = signal<string | null>(null);
  mostrarExternos = signal(false);

  sitioSel = signal<number | 'sin' | null>(null);

  readonly CARD_W = CARD_W;
  readonly CARD_H = CARD_H;

  sitios = computed<SitioOpt[]>(() => {
    const cuenta = new Map<number | 'sin', { nombre: string; n: number }>();
    for (const n of this.nodos()) {
      if (!n.es_recurso) continue;
      const id: number | 'sin' = n.sitio_id ?? 'sin';
      const prev = cuenta.get(id);
      if (prev) prev.n++;
      else cuenta.set(id, { nombre: n.sitio ?? 'Sin sede', n: 1 });
    }
    return [...cuenta.entries()]
      .map(([id, v]) => ({ id, nombre: v.nombre, n: v.n }))
      .sort((a, b) => b.n - a.n || a.nombre.localeCompare(b.nombre));
  });

  // ── Grafo jerárquico de la sede seleccionada ──────────────────────────
  grafo = computed<GrafoSede>(() => {
    const sel = this.sitioSel();
    if (sel === null) return { width: MIN_W, height: 200, nodos: [], bandas: [] };

    const ext = this.mostrarExternos();
    const recursosSede = this.nodos().filter((n) => n.es_recurso && (n.sitio_id ?? 'sin') === sel);
    const idsSede = new Set(recursosSede.map((n) => n.id));

    const ady = new Map<string, Set<string>>();
    const incluidos = new Map<string, TopologiaNodo>();
    recursosSede.forEach((n) => { incluidos.set(n.id, n); ady.set(n.id, new Set()); });
    const porId = new Map(this.nodos().map((n) => [n.id, n]));

    for (const e of this.enlaces()) {
      const aEnSede = idsSede.has(e.origen);
      const bEnSede = idsSede.has(e.destino);
      let a = e.origen, b = e.destino;
      if (aEnSede && bEnSede) {
        // enlace interno
      } else if (ext && aEnSede && porId.get(e.destino)?.es_recurso === false) {
        // recurso ↔ externo
      } else if (ext && bEnSede && porId.get(e.origen)?.es_recurso === false) {
        [a, b] = [e.destino, e.origen];
      } else {
        continue;
      }
      for (const id of [a, b]) {
        if (!incluidos.has(id)) { const nn = porId.get(id); if (nn) incluidos.set(id, nn); }
        if (!ady.has(id)) ady.set(id, new Set());
      }
      ady.get(a)!.add(b);
      ady.get(b)!.add(a);
    }

    const todos = [...incluidos.values()];
    const grado = (id: string) => ady.get(id)?.size ?? 0;

    // Niveles por BFS desde las raíces de mayor grado (núcleo arriba).
    const nivel = new Map<string, number>();
    const raices = todos.filter((n) => grado(n.id) > 0).sort((a, b) => grado(b.id) - grado(a.id));
    for (const raiz of raices) {
      if (nivel.has(raiz.id)) continue;
      const cola: string[] = [raiz.id];
      nivel.set(raiz.id, 0);
      while (cola.length) {
        const cur = cola.shift()!;
        const ln = nivel.get(cur)!;
        for (const vec of ady.get(cur) ?? []) {
          if (!nivel.has(vec)) { nivel.set(vec, ln + 1); cola.push(vec); }
        }
      }
    }
    const maxConectado = nivel.size ? Math.max(...nivel.values()) : -1;
    const bandaAislados = maxConectado + 1;
    todos.filter((n) => grado(n.id) === 0).forEach((n) => nivel.set(n.id, bandaAislados));

    // Posiciones por nivel.
    const porNivel = new Map<number, TopologiaNodo[]>();
    for (const n of todos) {
      const l = nivel.get(n.id)!;
      (porNivel.get(l) ?? porNivel.set(l, []).get(l)!).push(n);
    }
    const maxEnFila = Math.max(1, ...[...porNivel.values()].map((a) => a.length));
    const width = Math.max(MIN_W, maxEnFila * COL_W);

    const nodosPos: NodoPos[] = [];
    const bandas: Banda[] = [];
    for (const [l, arr] of [...porNivel.entries()].sort((a, b) => a[0] - b[0])) {
      arr.sort((a, b) => a.nombre.localeCompare(b.nombre));
      const k = arr.length;
      const y = TOP_PAD + l * NIVEL_H;
      arr.forEach((n, i) => nodosPos.push({ ...n, nivel: l, x: ((i + 1) * width) / (k + 1), y }));
      bandas.push({ y, label: this.etiquetaBanda(l, maxConectado, bandaAislados) });
    }

    const height = TOP_PAD + porNivel.size * NIVEL_H + 10;
    return { width, height, nodos: nodosPos, bandas };
  });

  private etiquetaBanda(l: number, maxConectado: number, aislados: number): string {
    if (l === aislados) return 'Sin enlaces LLDP';
    if (l === 0) return 'Núcleo';
    if (l === maxConectado) return 'Acceso';
    return 'Distribución';
  }

  private posMap = computed<Map<string, NodoPos>>(
    () => new Map(this.grafo().nodos.map((n) => [n.id, n])),
  );

  enlacesPos = computed<EnlacePos[]>(() => {
    const pos = this.posMap();
    const out: EnlacePos[] = [];
    for (const e of this.enlaces()) {
      const a = pos.get(e.origen);
      const b = pos.get(e.destino);
      if (!a || !b) continue;
      // Punto a ~26px del nodo, sobre la línea, para colocar el puerto.
      const dx = b.x - a.x, dy = b.y - a.y;
      const len = Math.hypot(dx, dy) || 1;
      const ux = dx / len, uy = dy / len;
      const off = Math.min(30, len * 0.32);
      out.push({
        origen: e.origen, destino: e.destino,
        x1: a.x, y1: a.y, x2: b.x, y2: b.y,
        pOrigen: e.origen_port ?? '', pDestino: e.destino_port ?? '',
        lox: a.x + ux * off, loy: a.y + uy * off,
        ldx: b.x - ux * off, ldy: b.y - uy * off,
      });
    }
    return out;
  });

  // Enlace "activo" si toca el nodo bajo el cursor o seleccionado.
  activo(e: EnlacePos): boolean {
    const k = this.hover() ?? this.seleccion();
    return !!k && (e.origen === k || e.destino === k);
  }

  hayResaltado = computed(() => !!(this.hover() ?? this.seleccion()));
  hayEnlaces = computed(() => this.enlacesPos().length > 0);

  ngOnInit(): void {
    this.svc.topologia().subscribe({
      next: (t) => {
        this.nodos.set(t.nodos);
        this.enlaces.set(t.enlaces);
        this.cargando.set(false);
        const s = this.sitios()[0];
        if (s) this.sitioSel.set(s.id);
      },
      error: () => this.cargando.set(false),
    });
  }

  claseNodo(n: TopologiaNodo): string {
    if (!n.es_recurso) return 'ext';
    return 'st-' + (n.estado ?? 'unknown');
  }

  tipoAbbr(n: TopologiaNodo): string {
    if (!n.es_recurso) return 'EXT';
    return (n.tipo && TIPO_INFO[n.tipo]?.abbr) || (n.tipo_nombre?.slice(0, 3).toUpperCase()) || '·';
  }

  tipoLabel(n: TopologiaNodo): string {
    if (!n.es_recurso) return 'Externo (no gestionado)';
    return (n.tipo && TIPO_INFO[n.tipo]?.label) || n.tipo_nombre || 'Recurso';
  }

  subtitulo(n: TopologiaNodo): string {
    return n.hostname || this.tipoLabel(n);
  }

  recorta(s: string, max: number): string {
    return s.length > max ? s.slice(0, max - 1) + '…' : s;
  }

  recursoId(id: string): number | null {
    return id.startsWith('r:') ? Number(id.slice(2)) : null;
  }

  nodoSel = computed<NodoPos | null>(() => {
    const s = this.seleccion();
    return s ? this.posMap().get(s) ?? null : null;
  });

  cambiarSitio(v: string): void {
    this.sitioSel.set(v === 'sin' ? 'sin' : Number(v));
    this.seleccion.set(null);
    this.hover.set(null);
  }
}
