import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { RecursosService } from '../../core/recursos.service';
import { TopologiaEnlace, TopologiaNodo } from '../../core/models';

interface NodoPos extends TopologiaNodo { x: number; y: number; }
interface EnlacePos { x1: number; y1: number; x2: number; y2: number; etiqueta: string; }

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

  // Layout circular: switches/recursos en el anillo interior, externos en el exterior.
  private R = computed(() => Math.max(170, this.nodos().length * 26));
  lienzo = computed(() => 2 * this.R() + 160);

  posiciones = computed<Map<string, NodoPos>>(() => {
    const ns = this.nodos();
    const recursos = ns.filter((n) => n.es_recurso);
    const externos = ns.filter((n) => !n.es_recurso);
    const c = this.lienzo() / 2;
    const map = new Map<string, NodoPos>();
    this.anillo(recursos, c, this.R() * 0.55, map);
    this.anillo(externos, c, this.R(), map);
    return map;
  });

  nodosPos = computed<NodoPos[]>(() => [...this.posiciones().values()]);

  enlacesPos = computed<EnlacePos[]>(() => {
    const pos = this.posiciones();
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

  private anillo(nodos: TopologiaNodo[], c: number, r: number, map: Map<string, NodoPos>): void {
    const n = nodos.length;
    nodos.forEach((nodo, i) => {
      // Si solo hay un nodo en el anillo interior, va al centro.
      if (n === 1 && r < this.R()) {
        map.set(nodo.id, { ...nodo, x: c, y: c });
        return;
      }
      const ang = (2 * Math.PI * i) / Math.max(1, n) - Math.PI / 2;
      map.set(nodo.id, { ...nodo, x: c + r * Math.cos(ang), y: c + r * Math.sin(ang) });
    });
  }

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

  recursoId(id: string): number | null {
    return id.startsWith('r:') ? Number(id.slice(2)) : null;
  }
}
