import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Dashboard, Estado, Incidencia, Recurso, Severidad, Sitio, TipoWidget, Widget } from '../../core/models';
import { DashboardsService } from '../../core/dashboards.service';
import { RecursosService } from '../../core/recursos.service';
import { TelemetriaService } from '../../core/telemetria.service';
import { WidgetMetrica } from './widget-metrica';
import { WidgetSyslog } from './widget-syslog';
import { duracion } from '../../shared/tiempo';

const PESO: Record<Estado, number> = { down: 5, degraded: 4, unknown: 3, maintenance: 2, up: 1 };
const SEVW: Record<Severidad, number> = { critical: 3, warning: 2, info: 1 };

@Component({
  selector: 'app-tableros',
  standalone: true,
  imports: [FormsModule, WidgetMetrica, WidgetSyslog],
  templateUrl: './tableros.html',
  styleUrl: './tableros.scss',
})
export class Tableros implements OnInit {
  private svc = inject(DashboardsService);
  private recursosSvc = inject(RecursosService);
  private tele = inject(TelemetriaService);
  duracion = duracion;

  dashboards = signal<Dashboard[]>([]);
  activo = signal<Dashboard | null>(null);
  editando = signal(false);
  cargando = signal(true);

  // Datos compartidos para los widgets ligeros.
  recursos = signal<Recurso[]>([]);
  sitios = signal<Sitio[]>([]);
  incidencias = signal<Incidencia[]>([]);

  readonly tiposWidget: { id: TipoWidget; label: string }[] = [
    { id: 'kpis', label: 'KPIs (estado general)' },
    { id: 'estado_sitio', label: 'Semáforo por sitio' },
    { id: 'incidencias', label: 'Incidencias activas' },
    { id: 'metrica', label: 'Métrica de un recurso' },
    { id: 'syslog', label: 'Syslog reciente' },
  ];

  ngOnInit(): void {
    this.recursosSvc.sitios().subscribe((p) => this.sitios.set(p.data));
    this.recursosSvc.listar().subscribe((p) => this.recursos.set(p.data));
    this.tele.incidencias({ activas: true, per_page: 200 }).subscribe((p) => this.incidencias.set(p.data));
    this.cargar();
  }

  private cargar(): void {
    this.cargando.set(true);
    this.svc.listar().subscribe({
      next: (r) => {
        this.dashboards.set(r.data);
        this.activo.set(r.data.find((d) => d.es_default) ?? r.data[0] ?? null);
        this.cargando.set(false);
      },
      error: () => this.cargando.set(false),
    });
  }

  seleccionar(d: Dashboard): void { this.activo.set(d); this.editando.set(false); }
  seleccionarPorId(id: number): void {
    const d = this.dashboards().find((x) => x.id === id);
    if (d) this.seleccionar(d);
  }

  // ── KPIs / semáforo / incidencias (desde datos compartidos) ──
  kpis = computed(() => {
    const rs = this.recursos();
    const cuenta = (e: Estado) => rs.filter((r) => r.estado_actual === e).length;
    const inc = this.incidencias();
    return {
      total: rs.length, up: cuenta('up'), degraded: cuenta('degraded'), down: cuenta('down'),
      inc: inc.length, crit: inc.filter((i) => i.severidad === 'critical').length,
    };
  });

  gruposSitio = computed(() => {
    const porSitio = new Map<number | string, { nombre: string; estado: Estado; total: number; down: number }>();
    const nombreSitio = (id?: number | null) => this.sitios().find((s) => s.id === id)?.nombre ?? 'Sin sitio';
    for (const r of this.recursos()) {
      const k = r.sitio_id ?? 'sin';
      const g = porSitio.get(k) ?? { nombre: nombreSitio(r.sitio_id), estado: 'up' as Estado, total: 0, down: 0 };
      g.total++;
      if (r.estado_actual === 'down') g.down++;
      if (PESO[r.estado_actual] > PESO[g.estado]) g.estado = r.estado_actual;
      porSitio.set(k, g);
    }
    return [...porSitio.values()].sort((a, b) => PESO[b.estado] - PESO[a.estado] || b.total - a.total);
  });

  incidenciasW(w: Widget): Incidencia[] {
    let xs = this.incidencias();
    if (w.severidad) xs = xs.filter((i) => i.severidad === w.severidad);
    return [...xs].sort((a, b) => SEVW[b.severidad] - SEVW[a.severidad]
      || +new Date(a.abierta_at) - +new Date(b.abierta_at)).slice(0, w.limite ?? 8);
  }

  color(e: Estado): string {
    return { up: '#1b8a3a', degraded: '#e0a400', down: '#d11d1d', unknown: '#9aa0a6', maintenance: '#3b82f6' }[e];
  }
  colorSev(s: Severidad): string { return { critical: '#d11d1d', warning: '#e0a400', info: '#9aa0a6' }[s]; }
  anchoClase(w: Widget): string { return 'w' + (w.ancho ?? 1); }
  labelTipo(tipo: TipoWidget): string {
    return this.tiposWidget.find((t) => t.id === tipo)?.label ?? tipo;
  }

  // ── Edición del tablero ──
  nuevoTablero(): void {
    const nombre = prompt('Nombre del tablero:')?.trim();
    if (!nombre) return;
    this.svc.crear({ nombre, es_default: this.dashboards().length === 0, widgets: [] })
      .subscribe(() => this.cargar());
  }
  renombrar(): void {
    const d = this.activo(); if (!d) return;
    const nombre = prompt('Nuevo nombre:', d.nombre)?.trim();
    if (!nombre) return;
    d.nombre = nombre; this.guardar();
  }
  eliminarTablero(): void {
    const d = this.activo(); if (!d) return;
    if (!confirm(`¿Eliminar el tablero "${d.nombre}"?`)) return;
    this.svc.eliminar(d.id).subscribe(() => { this.activo.set(null); this.cargar(); });
  }
  marcarDefault(): void { const d = this.activo(); if (d) { d.es_default = true; this.guardar(); } }

  addWidget(tipo: TipoWidget): void {
    const d = this.activo(); if (!d) return;
    const base: Widget = { tipo, ancho: tipo === 'kpis' ? 3 : (tipo === 'metrica' ? 2 : 1) };
    if (tipo === 'incidencias') { base.limite = 8; base.severidad = ''; }
    if (tipo === 'syslog') { base.limite = 10; base.severidad = ''; }
    if (tipo === 'metrica') { base.rango = '24h'; base.metrica = 'cpu'; }
    d.widgets = [...d.widgets, base];
    this.activo.set({ ...d });
  }
  quitarWidget(i: number): void {
    const d = this.activo(); if (!d) return;
    d.widgets.splice(i, 1); this.activo.set({ ...d });
  }
  mover(i: number, dir: number): void {
    const d = this.activo(); if (!d) return;
    const j = i + dir; if (j < 0 || j >= d.widgets.length) return;
    [d.widgets[i], d.widgets[j]] = [d.widgets[j], d.widgets[i]]; this.activo.set({ ...d });
  }
  guardar(): void {
    const d = this.activo(); if (!d) return;
    this.svc.actualizar(d.id, { nombre: d.nombre, es_default: d.es_default, widgets: d.widgets })
      .subscribe(() => { this.editando.set(false); this.cargar(); });
  }

  recursosConMetricas = computed(() => this.recursos());
}
