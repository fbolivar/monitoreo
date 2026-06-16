import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Estado, Recurso, Sitio } from '../../core/models';
import { RecursosService } from '../../core/recursos.service';

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

// Contorno simplificado de Colombia (lon, lat). Se proyecta con la MISMA
// función equirectangular que los marcadores, por lo que quedan alineados.
const COLOMBIA: [number, number][] = [
  [-71.66, 12.46], [-72.6, 11.7], [-73.4, 11.3], [-74.2, 11.24], [-74.85, 11.1],
  [-75.53, 10.4], [-76.25, 9.4], [-76.9, 8.6], [-77.35, 8.67], [-77.5, 7.5],
  [-77.3, 6.5], [-77.45, 5.6], [-77.2, 4.3], [-78.2, 2.6], [-78.86, 1.45],
  [-77.7, 0.65], [-76.4, 0.38], [-75.2, -0.15], [-74.0, -0.9], [-71.2, -2.3],
  [-70.05, -4.2], [-69.6, -1.3], [-69.4, 1.07], [-67.3, 1.75], [-66.87, 1.23],
  [-67.0, 2.8], [-67.85, 5.3], [-69.4, 6.1], [-70.1, 6.95], [-72.0, 7.1],
  [-72.45, 8.35], [-72.9, 9.1], [-72.5, 10.5], [-71.9, 11.5],
];

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

  outline = COLOMBIA.map(([lon, lat]) => this.proj(lon, lat));
  outlinePath = 'M ' + this.outline.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' L ') + ' Z';

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

  // Radio según número de recursos (mínimo legible, tope para no tapar).
  radio(s: Sede): number {
    return Math.max(9, Math.min(20, 8 + Math.sqrt(s.total) * 3));
  }

  hayProblema(s: Sede): boolean {
    return s.down > 0 || s.degraded > 0;
  }
}
