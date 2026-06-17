import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { RecursosService } from '../../core/recursos.service';
import { TopologiaEnlace, TopologiaNodo } from '../../core/models';

interface NodoPos extends TopologiaNodo { x: number; y: number; }
interface CajaSitio { x: number; y: number; w: number; h: number; titulo: string; n: number; }
interface EnlacePos { x1: number; y1: number; x2: number; y2: number; etiqueta: string; }
interface Layout { width: number; height: number; cajas: CajaSitio[]; nodos: NodoPos[]; }

// Geometría del layout agrupado por sitio.
const CELL_W = 104;
const CELL_H = 74;
const PAD = 16;
const HEADER_H = 28;
const GAP = 22;
const CANVAS_W = 1180;
const MAX_COLS = 6;
const R = 14;

@Component({
  selector: 'app-topologia',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './topologia.html',
  styleUrl: './topologia.scss',
})
export class Topologia implements OnInit {
  private svc = inject(RecursosService);

  nodos = signal<TopologiaNodo[]>([]);
  enlaces = signal<TopologiaEnlace[]>([]);
  cargando = signal(true);
  seleccion = signal<string | null>(null);

  // Controles de visualización.
  mostrarExternos = signal(false);   // los vecinos no gestionados son ruidosos (cientos) → ocultos por defecto.
  soloEnlazados = signal(false);     // ocultar recursos sin ningún vecino LLDP.

  totalExternos = computed(() => this.nodos().filter((n) => !n.es_recurso).length);
  totalRecursos = computed(() => this.nodos().filter((n) => n.es_recurso).length);

  // Nodos visibles según los toggles.
  nodosVisibles = computed<TopologiaNodo[]>(() => {
    const ext = this.mostrarExternos();
    const solo = this.soloEnlazados();
    return this.nodos().filter((n) => {
      if (!n.es_recurso && !ext) return false;
      if (solo && (n.grado ?? 0) === 0) return false;
      return true;
    });
  });

  // Layout: agrupa por sitio, cada grupo en su caja, las cajas se empacan en filas.
  layout = computed<Layout>(() => {
    const visibles = this.nodosVisibles();

    // Agrupar: recursos por sitio; los externos en su propio grupo al final.
    const grupos = new Map<string, TopologiaNodo[]>();
    for (const n of visibles) {
      const clave = n.es_recurso ? (n.sitio ?? 'Sin sitio') : '⌁ Externos (no gestionados)';
      (grupos.get(clave) ?? grupos.set(clave, []).get(clave)!).push(n);
    }
    const claves = [...grupos.keys()].sort((a, b) => {
      const ea = a.startsWith('⌁'), eb = b.startsWith('⌁');
      if (ea !== eb) return ea ? 1 : -1;          // externos al final
      return a.localeCompare(b);
    });

    const cajas: CajaSitio[] = [];
    const nodosPos: NodoPos[] = [];
    let cx = GAP, cy = GAP, filaAlto = 0;

    for (const clave of claves) {
      const items = grupos.get(clave)!.slice().sort((a, b) => a.nombre.localeCompare(b.nombre));
      const cols = Math.min(MAX_COLS, Math.max(1, Math.ceil(Math.sqrt(items.length))));
      const rows = Math.ceil(items.length / cols);
      const bw = cols * CELL_W + PAD * 2;
      const bh = HEADER_H + rows * CELL_H + PAD;

      // Salto de fila si no cabe.
      if (cx + bw > CANVAS_W && cx > GAP) { cx = GAP; cy += filaAlto + GAP; filaAlto = 0; }

      cajas.push({ x: cx, y: cy, w: bw, h: bh, titulo: clave, n: items.length });

      items.forEach((nodo, i) => {
        const col = i % cols, row = Math.floor(i / cols);
        const nx = cx + PAD + col * CELL_W + CELL_W / 2;
        const ny = cy + HEADER_H + row * CELL_H + R + 8;
        nodosPos.push({ ...nodo, x: nx, y: ny });
      });

      cx += bw + GAP;
      filaAlto = Math.max(filaAlto, bh);
    }

    const width = CANVAS_W;
    const height = cy + filaAlto + GAP;
    return { width, height, cajas, nodos: nodosPos };
  });

  private posMap = computed<Map<string, NodoPos>>(
    () => new Map(this.layout().nodos.map((n) => [n.id, n])),
  );

  enlacesPos = computed<EnlacePos[]>(() => {
    const pos = this.posMap();
    const out: EnlacePos[] = [];
    for (const e of this.enlaces()) {
      const a = pos.get(e.origen);
      const b = pos.get(e.destino);
      if (!a || !b) continue;   // alguno está oculto por los toggles
      out.push({
        x1: a.x, y1: a.y, x2: b.x, y2: b.y,
        etiqueta: `${e.origen_port ?? ''} ↔ ${e.destino_port ?? ''}`,
      });
    }
    return out;
  });

  ngOnInit(): void {
    this.svc.topologia().subscribe({
      next: (t) => { this.nodos.set(t.nodos); this.enlaces.set(t.enlaces); this.cargando.set(false); },
      error: () => this.cargando.set(false),
    });
  }

  claseNodo(n: TopologiaNodo): string {
    if (!n.es_recurso) return 'ext';
    return 'st-' + (n.estado ?? 'unknown');
  }

  // Recorta el nombre para que quepa bajo el nodo.
  etiqueta(nombre: string): string {
    return nombre.length > 16 ? nombre.slice(0, 15) + '…' : nombre;
  }

  recursoId(id: string): number | null {
    return id.startsWith('r:') ? Number(id.slice(2)) : null;
  }

  nodoSel = computed<NodoPos | null>(() => {
    const s = this.seleccion();
    return s ? this.posMap().get(s) ?? null : null;
  });
}
