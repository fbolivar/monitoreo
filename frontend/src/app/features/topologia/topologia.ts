import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { RecursosService } from '../../core/recursos.service';
import { TopologiaEnlace, TopologiaNodo } from '../../core/models';
import { Mapa } from '../mapa/mapa';

interface NodoPos extends TopologiaNodo { x: number; y: number; nivel: number; }
interface EnlacePos { x1: number; y1: number; x2: number; y2: number; etiqueta: string; }
interface SitioOpt { id: number | 'sin'; nombre: string; n: number; }
interface GrafoSede { width: number; height: number; nodos: NodoPos[]; niveles: number; }

// Geometría del grafo jerárquico.
const NIVEL_H = 116;
const TOP_PAD = 46;
const MIN_W = 760;
const COL_W = 150;
const R = 15;

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
  mostrarExternos = signal(false);   // vecinos no gestionados (ruidosos) → ocultos por defecto.

  sitioSel = signal<number | 'sin' | null>(null);

  // Sedes que tienen al menos un recurso (para el selector del Tab 2).
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
    if (sel === null) return { width: MIN_W, height: 200, nodos: [], niveles: 0 };

    const ext = this.mostrarExternos();

    // 1) Nodos candidatos: recursos de la sede + (opc.) externos conectados a ellos.
    const recursosSede = this.nodos().filter(
      (n) => n.es_recurso && (n.sitio_id ?? 'sin') === sel,
    );
    const idsSede = new Set(recursosSede.map((n) => n.id));

    // Adyacencia restringida a la sede (+ externos si toca).
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
        // recurso de la sede ↔ externo
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

    // 2) Niveles por BFS desde las raíces de mayor grado (núcleo arriba).
    const nivel = new Map<string, number>();
    const raices = todos
      .filter((n) => grado(n.id) > 0)
      .sort((a, b) => grado(b.id) - grado(a.id));
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
    // Aislados (sin LLDP): a una banda al fondo para no perderlos de vista.
    const maxNivel = nivel.size ? Math.max(...nivel.values()) : -1;
    const bandaAislados = maxNivel + 1;
    const aislados = todos.filter((n) => grado(n.id) === 0);
    aislados.forEach((n) => nivel.set(n.id, bandaAislados));

    // 3) Posiciones por nivel.
    const porNivel = new Map<number, TopologiaNodo[]>();
    for (const n of todos) {
      const l = nivel.get(n.id)!;
      (porNivel.get(l) ?? porNivel.set(l, []).get(l)!).push(n);
    }
    const maxEnFila = Math.max(1, ...[...porNivel.values()].map((a) => a.length));
    const width = Math.max(MIN_W, maxEnFila * COL_W);

    const nodosPos: NodoPos[] = [];
    for (const [l, arr] of porNivel) {
      arr.sort((a, b) => a.nombre.localeCompare(b.nombre));
      const k = arr.length;
      arr.forEach((n, i) => {
        nodosPos.push({ ...n, nivel: l, x: ((i + 1) * width) / (k + 1), y: TOP_PAD + l * NIVEL_H });
      });
    }

    const niveles = porNivel.size;
    const height = TOP_PAD + Math.max(0, niveles) * NIVEL_H + 30;
    return { width, height, nodos: nodosPos, niveles };
  });

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
      out.push({
        x1: a.x, y1: a.y, x2: b.x, y2: b.y,
        etiqueta: `${e.origen_port ?? ''} ↔ ${e.destino_port ?? ''}`,
      });
    }
    return out;
  });

  // Banda de aislados (para etiquetar "sin enlaces").
  bandaAislados = computed<number | null>(() => {
    const niveles = this.grafo().nodos.map((n) => n.nivel);
    const aislados = this.grafo().nodos.filter((n) => (n.grado ?? 0) === 0);
    if (!aislados.length || !niveles.length) return null;
    return Math.max(...niveles);
  });

  hayEnlaces = computed(() => this.enlacesPos().length > 0);

  ngOnInit(): void {
    this.svc.topologia().subscribe({
      next: (t) => {
        this.nodos.set(t.nodos);
        this.enlaces.set(t.enlaces);
        this.cargando.set(false);
        // Selecciona por defecto la sede con más recursos.
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

  etiqueta(nombre: string): string {
    return nombre.length > 18 ? nombre.slice(0, 17) + '…' : nombre;
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
  }
}
