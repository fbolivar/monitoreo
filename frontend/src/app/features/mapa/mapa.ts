import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Estado, Recurso, Sitio } from '../../core/models';
import { RecursosService } from '../../core/recursos.service';

interface Marcador {
  sitio: Sitio;
  x: number;
  y: number;
  estado: Estado;
  total: number;
  caidos: number;
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

  outline = COLOMBIA.map(([lon, lat]) => this.proj(lon, lat));
  outlinePath = 'M ' + this.outline.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' L ') + ' Z';

  marcadores = computed<Marcador[]>(() => {
    const porSitio = new Map<number, Recurso[]>();
    for (const r of this.recursos()) {
      if (r.sitio_id == null) continue;
      (porSitio.get(r.sitio_id) ?? porSitio.set(r.sitio_id, []).get(r.sitio_id)!).push(r);
    }
    return this.sitios()
      .filter((s) => s.latitud != null && s.longitud != null)
      .map((s) => {
        const rs = porSitio.get(s.id) ?? [];
        const estado = rs.reduce<Estado>(
          (peor, r) => (PESO[r.estado_actual] > PESO[peor] ? r.estado_actual : peor), 'up');
        const p = this.proj(s.longitud!, s.latitud!);
        return {
          sitio: s, x: p.x, y: p.y,
          estado: rs.length ? estado : 'unknown',
          total: rs.length,
          caidos: rs.filter((r) => r.estado_actual === 'down').length,
        };
      });
  });

  sinCoords = computed(() => this.sitios().filter((s) => s.latitud == null || s.longitud == null));

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

  // Radio según número de recursos (mínimo legible).
  radio(m: Marcador): number {
    return Math.min(16, 7 + m.total);
  }
}
