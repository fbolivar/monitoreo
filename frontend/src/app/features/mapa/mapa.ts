import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Estado, Recurso, Sitio } from '../../core/models';
import { RecursosService } from '../../core/recursos.service';
import { COLOMBIA_DEPARTAMENTOS } from './colombia-geo';

interface Sede {
  sitio: Sitio;
  estado: Estado;          // peor estado de sus recursos
  total: number;
  up: number;
  degraded: number;
  down: number;
  otros: number;           // unknown + maintenance
  x: number | null;        // proyección (null si la sede no tiene coordenadas)
  y: number | null;
}

const PESO: Record<Estado, number> = { down: 5, degraded: 4, unknown: 3, maintenance: 2, up: 1 };

@Component({
  selector: 'app-mapa',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './mapa.html',
  styleUrl: './mapa.scss',
})
export class Mapa implements OnInit {
  private svc = inject(RecursosService);

  readonly W = 437;
  readonly H = 600;
  private readonly LON_MIN = -79.1;
  private readonly LON_MAX = -66.8;
  private readonly LAT_MIN = -4.3;
  private readonly LAT_MAX = 12.6;

  sitios = signal<Sitio[]>([]);
  recursos = signal<Recurso[]>([]);
  cargando = signal(true);
  hoverId = signal<number | null>(null);   // sincroniza marcador <-> fila de la lista

  // Mapa vectorial real: departamentos de Colombia (ya proyectados con la misma proj).
  departamentos = COLOMBIA_DEPARTAMENTOS;

  // Todas las sedes con sus conteos (tengan o no coordenadas).
  sedes = computed<Sede[]>(() => {
    const porSitio = new Map<number, Recurso[]>();
    for (const r of this.recursos()) {
      if (r.sitio_id == null) continue;
      (porSitio.get(r.sitio_id) ?? porSitio.set(r.sitio_id, []).get(r.sitio_id)!).push(r);
    }
    return this.sitios().map((s) => {
      const rs = porSitio.get(s.id) ?? [];
      const peor = rs.reduce<Estado>(
        (acc, r) => (PESO[r.estado_actual] > PESO[acc] ? r.estado_actual : acc), 'up');
      const cuenta = (e: Estado) => rs.filter((r) => r.estado_actual === e).length;
      const tieneCoords = s.latitud != null && s.longitud != null;
      const p = tieneCoords ? this.proj(s.longitud!, s.latitud!) : null;
      return {
        sitio: s,
        estado: rs.length ? peor : 'unknown',
        total: rs.length,
        up: cuenta('up'),
        degraded: cuenta('degraded'),
        down: cuenta('down'),
        otros: cuenta('unknown') + cuenta('maintenance'),
        x: p ? p.x : null,
        y: p ? p.y : null,
      };
    });
  });

  // Marcadores: solo las sedes con coordenadas.
  marcadores = computed<Sede[]>(() => this.sedes().filter((s) => s.x != null));

  // Lista: peor estado primero, luego más recursos primero.
  sedesOrdenadas = computed<Sede[]>(() =>
    [...this.sedes()].sort((a, b) =>
      PESO[b.estado] - PESO[a.estado] || b.total - a.total || a.sitio.nombre.localeCompare(b.sitio.nombre)),
  );

  // KPIs de cabecera.
  totalSedes = computed(() => this.sedes().length);
  sedesConProblemas = computed(() => this.sedes().filter((s) => s.down > 0 || s.degraded > 0).length);
  recursosCaidos = computed(() => this.sedes().reduce((n, s) => n + s.down, 0));

  ngOnInit(): void {
    this.svc.sitios().subscribe((p) => this.sitios.set(p.data));
    this.svc.listar().subscribe({
      next: (p) => { this.recursos.set(p.data); this.cargando.set(false); },
      error: () => this.cargando.set(false),
    });
  }

  private proj(lon: number, lat: number): { x: number; y: number } {
    return {
      x: (lon - this.LON_MIN) / (this.LON_MAX - this.LON_MIN) * this.W,
      y: (this.LAT_MAX - lat) / (this.LAT_MAX - this.LAT_MIN) * this.H,
    };
  }

  color(estado: Estado): string {
    return { up: '#1b8a3a', degraded: '#e0a400', down: '#d11d1d',
             unknown: '#9aa0a6', maintenance: '#3b82f6' }[estado];
  }

  // Radio compacto: con 80+ sedes, las operativas van pequeñas y las que tienen
  // problema (o varios recursos) un poco más grandes para resaltar.
  radio(s: Sede): number {
    if (s.down > 0 || s.degraded > 0) return 10;
    return Math.max(5, Math.min(11, 4 + Math.sqrt(s.total) * 2));
  }

  hayProblema(s: Sede): boolean {
    return s.down > 0 || s.degraded > 0;
  }
}
