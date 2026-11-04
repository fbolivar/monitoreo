import { Component, OnDestroy, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { Incidencia, RelevoTurno, Severidad } from '../../core/models';
import { AuthService } from '../../core/auth.service';
import { TelemetriaService } from '../../core/telemetria.service';
import { duracion, fecha } from '../../shared/tiempo';

const SEV: Record<Severidad, number> = { critical: 3, warning: 2, info: 1 };

/**
 * Consola de alarmas del NOC: vista operativa en vivo de las incidencias no
 * resueltas, con flujo del operador (reconocer, tomar, silenciar, resolver),
 * acciones en lote y relevo de turno. Autorrefresco por polling.
 */
@Component({
  selector: 'app-consola',
  standalone: true,
  imports: [FormsModule, RouterLink],
  templateUrl: './consola.html',
  styleUrl: './consola.scss',
})
export class Consola implements OnInit, OnDestroy {
  private tele = inject(TelemetriaService);
  auth = inject(AuthService);
  fecha = fecha;
  duracion = duracion;

  alarmas = signal<Incidencia[]>([]);
  relevos = signal<RelevoTurno[]>([]);
  cargando = signal(true);
  error = signal<string | null>(null);
  procesando = signal(false);

  filtroAsignado = signal<'todas' | 'mias' | 'sin'>('todas');
  filtroSev = signal<'' | Severidad>('');
  seleccion = signal<Set<number>>(new Set());

  // Relevo de turno
  mostrarRelevo = signal(false);
  resumenRelevo = signal('');

  private timer: ReturnType<typeof setInterval> | null = null;
  private readonly REFRESCO_MS = 15000;

  private yo = computed(() => this.auth.perfil()?.id ?? null);

  filtradas = computed<Incidencia[]>(() => {
    const sev = this.filtroSev();
    const asg = this.filtroAsignado();
    const yo = this.yo();
    return this.alarmas()
      .filter((a) => {
        if (sev && a.severidad !== sev) return false;
        if (asg === 'mias' && a.asignado_a !== yo) return false;
        if (asg === 'sin' && a.asignado_a) return false;
        return true;
      })
      .sort((a, b) => SEV[b.severidad] - SEV[a.severidad]
        || +new Date(a.abierta_at) - +new Date(b.abierta_at));
  });

  // KPIs
  criticas = computed(() => this.alarmas().filter((a) => a.severidad === 'critical').length);
  sinAsignar = computed(() => this.alarmas().filter((a) => !a.asignado_a).length);
  sinReconocer = computed(() => this.alarmas().filter((a) => a.estado === 'abierta').length);

  ngOnInit(): void {
    this.cargar();
    this.cargarRelevos();
    this.timer = setInterval(() => this.cargar(true), this.REFRESCO_MS);
  }
  ngOnDestroy(): void { if (this.timer) clearInterval(this.timer); }

  private cargar(silencioso = false): void {
    if (!silencioso) this.cargando.set(true);
    this.tele.incidencias({ activas: true, per_page: 500 }).subscribe({
      next: (p) => { this.alarmas.set(p.data); this.cargando.set(false); },
      error: () => { if (!silencioso) this.error.set('No se pudieron cargar las alarmas.'); this.cargando.set(false); },
    });
  }
  private cargarRelevos(): void {
    this.tele.relevos(10).subscribe({ next: (r) => this.relevos.set(r.data), error: () => {} });
  }

  // ── Selección ──
  sel(id: number): boolean { return this.seleccion().has(id); }
  toggleSel(id: number): void {
    const s = new Set(this.seleccion());
    s.has(id) ? s.delete(id) : s.add(id);
    this.seleccion.set(s);
  }
  toggleTodas(): void {
    const vis = this.filtradas().map((a) => a.id);
    const s = this.seleccion();
    this.seleccion.set(vis.every((id) => s.has(id)) ? new Set() : new Set(vis));
  }
  limpiarSel(): void { this.seleccion.set(new Set()); }

  // ── Acciones individuales ──
  reconocer(a: Incidencia): void { this.una(this.tele.reconocerIncidencia(a.id)); }
  resolver(a: Incidencia): void {
    if (!confirm(`¿Resolver la alarma "${a.titulo}"?`)) return;
    this.una(this.tele.resolverIncidencia(a.id));
  }
  tomar(a: Incidencia): void { this.una(this.tele.asignarIncidencia(a.id, { mi: true })); }
  liberar(a: Incidencia): void { this.una(this.tele.asignarIncidencia(a.id, { perfil_id: null })); }
  silenciar(a: Incidencia, minutos: number): void { this.una(this.tele.silenciarIncidencia(a.id, minutos)); }

  private una(obs: { subscribe: (o: { next: () => void; error: () => void }) => void }): void {
    this.procesando.set(true);
    obs.subscribe({
      next: () => { this.procesando.set(false); this.cargar(true); },
      error: () => { this.procesando.set(false); alert('No se pudo aplicar la acción.'); },
    });
  }

  // ── Acciones en lote ──
  lote(accion: 'reconocer' | 'tomar' | 'silenciar' | 'resolver', minutos?: number): void {
    const ids = [...this.seleccion()];
    if (ids.length === 0) return;
    if (accion === 'resolver' && !confirm(`¿Resolver ${ids.length} alarma(s)?`)) return;
    this.procesando.set(true);
    this.tele.accionesIncidencias(ids, accion, minutos).subscribe({
      next: () => { this.procesando.set(false); this.limpiarSel(); this.cargar(true); },
      error: () => { this.procesando.set(false); alert('No se pudieron aplicar las acciones.'); },
    });
  }

  // ── Relevo de turno ──
  guardarRelevo(): void {
    const t = this.resumenRelevo().trim();
    if (!t) return;
    this.procesando.set(true);
    this.tele.crearRelevo(t).subscribe({
      next: () => {
        this.procesando.set(false); this.resumenRelevo.set(''); this.mostrarRelevo.set(false);
        this.cargarRelevos();
      },
      error: () => { this.procesando.set(false); alert('No se pudo registrar el relevo.'); },
    });
  }

  // ── Helpers de presentación ──
  colorSev(s: Severidad): string {
    return { critical: '#d11d1d', warning: '#e0a400', info: '#9aa0a6' }[s];
  }
  silenciada(a: Incidencia): boolean {
    return !!a.silenciado_hasta && new Date(a.silenciado_hasta) > new Date();
  }
  nombreOperador(a: Incidencia): string {
    return a.operador?.nombre || a.operador?.email || '';
  }
  mia(a: Incidencia): boolean { return !!a.asignado_a && a.asignado_a === this.yo(); }
}
