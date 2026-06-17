import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../../core/auth.service';
import {
  ComponenteAnalisis, Estado, Recurso, ServicioAnalisis, TIPOS_COMPONENTE, TipoComponente,
} from '../../core/models';
import { RecursosService } from '../../core/recursos.service';
import { ServiciosService } from '../../core/servicios.service';

interface FormComp { nombre: string; tipo: TipoComponente; recurso_id: number | null; umbral_ms: number | null; }

const PESO: Record<Estado, number> = { down: 5, degraded: 4, unknown: 3, maintenance: 2, up: 1 };

@Component({
  selector: 'app-servicios',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './servicios.html',
  styleUrl: './servicios.scss',
})
export class Servicios implements OnInit {
  private svc = inject(ServiciosService);
  private recSvc = inject(RecursosService);
  auth = inject(AuthService);

  readonly tipos = TIPOS_COMPONENTE;

  lista = signal<ServicioAnalisis[]>([]);
  sel = signal<ServicioAnalisis | null>(null);
  recursos = signal<Recurso[]>([]);
  cargando = signal(true);
  error = signal<string | null>(null);

  // Form
  editId = signal<number | null>(null);
  creando = signal(false);
  fServ = this.vacio();

  // Latencia máxima entre componentes (para escalar el waterfall).
  maxLat = computed(() => {
    const cs = this.sel()?.componentes ?? [];
    return Math.max(1, ...cs.map((c) => c.latencia_ms ?? 0));
  });

  // ── Cockpit: resumen + orden peor-primero ──
  listaOrdenada = computed<ServicioAnalisis[]>(() =>
    [...this.lista()].sort((a, b) => {
      if (PESO[b.estado] !== PESO[a.estado]) return PESO[b.estado] - PESO[a.estado];
      if (a.alto_impacto !== b.alto_impacto) return a.alto_impacto ? -1 : 1;
      return (b.experiencia_ms ?? 0) - (a.experiencia_ms ?? 0);
    }),
  );
  totalSvc = computed(() => this.lista().length);
  afectados = computed(() => this.lista().filter((s) => s.alto_impacto).length);
  sanos = computed(() => this.lista().filter((s) => !s.alto_impacto).length);

  ngOnInit(): void {
    this.recSvc.listar({ per_page: 200 }).subscribe((p) => this.recursos.set(p.data));
    this.cargar();
  }

  private cargar(): void {
    this.cargando.set(true);
    this.svc.lista().subscribe({
      next: (s) => {
        this.lista.set(s);
        this.cargando.set(false);
        // Mantener o elegir selección.
        const actual = this.sel();
        const id = actual ? actual.id : s[0]?.id;
        if (id != null) this.verAnalisis(id);
      },
      error: () => { this.error.set('No se pudieron cargar los servicios.'); this.cargando.set(false); },
    });
  }

  verAnalisis(id: number): void {
    this.svc.analisis(id).subscribe({ next: (a) => this.sel.set(a) });
  }

  // ── Helpers de presentación ───────────────────────────────────────
  color(e: Estado): string {
    return { up: '#1b8a3a', degraded: '#e0a400', down: '#d11d1d',
             unknown: '#9aa0a6', maintenance: '#3b82f6' }[e];
  }
  fmtMs(ms: number | null | undefined): string {
    if (ms == null) return '—';
    return ms >= 1000 ? (ms / 1000).toFixed(2) + ' s' : Math.round(ms) + ' ms';
  }
  estadoLabel(e: Estado): string {
    return { up: 'operativo', degraded: 'degradado', down: 'caído',
             unknown: 'sin datos', maintenance: 'mantenim.' }[e];
  }
  // ¿La latencia de entrada supera el objetivo? (impacto por lentitud real)
  expLenta(a: ServicioAnalisis): boolean {
    return a.experiencia_ms != null && a.experiencia_ms > a.objetivo_ms;
  }
  // Texto del flag de impacto: distingue lentitud real de dependencia mal-sana.
  flagImpacto(a: ServicioAnalisis): string {
    if (this.expLenta(a)) return 'Experiencia lenta';
    if (a.estado === 'down') return 'Dependencia caída';
    if (a.estado === 'degraded') return 'Dependencia degradada';
    return 'Dentro del objetivo';
  }
  // Nivel de urgencia para priorizar (color del cockpit).
  accionNivel(a: ServicioAnalisis): 'urgente' | 'medio' | 'ok' {
    if (a.estado === 'down' || a.estado === 'degraded') return 'urgente';
    if (this.expLenta(a)) return 'medio';
    return 'ok';
  }
  // Acción recomendada legible para tomar la decisión.
  accion(a: ServicioAnalisis): string {
    const cu = a.cuello?.nombre ?? 'el componente más afectado';
    const causa = a.causa ? ` (${a.causa})` : '';
    if (a.estado === 'down') return `Atender ya: ${cu} está caído${causa}.`;
    if (a.estado === 'degraded') return `Atender: ${cu} degradado${causa}.`;
    if (this.expLenta(a)) {
      return `Optimizar ${cu}: la experiencia (${this.fmtMs(a.experiencia_ms)}) supera el objetivo (${this.fmtMs(a.objetivo_ms)}).`;
    }
    return `Sin acción urgente; vigilar ${cu} (salto más lento).`;
  }
  anchoBarra(ms: number | null): number {
    return ms == null ? 0 : Math.max(2, Math.round((ms / this.maxLat()) * 100));
  }
  esCuello(c: ComponenteAnalisis): boolean {
    const cu = this.sel()?.cuello;
    return !!cu && cu.nombre === c.nombre && cu.recurso_id === c.recurso_id;
  }
  icono(t: TipoComponente): string {
    return { web: '🌐', api: '🔌', gateway: '🚪', cache: '⚡', db: '🗄️', externo: '☁️', servicio: '⚙️' }[t];
  }

  // ── CRUD ──────────────────────────────────────────────────────────
  private vacio() {
    return {
      nombre: '', descripcion: '', objetivo_ms: 2000, impacto_negocio: '', activo: true,
      componentes: [
        { nombre: 'Web', tipo: 'web' as TipoComponente, recurso_id: null, umbral_ms: null },
        { nombre: 'Base de Datos', tipo: 'db' as TipoComponente, recurso_id: null, umbral_ms: null },
      ] as FormComp[],
    };
  }
  nuevo(): void { this.creando.set(true); this.editId.set(null); this.error.set(null); this.fServ = this.vacio(); }
  editar(): void {
    const s = this.sel();
    if (!s) return;
    this.error.set(null);
    this.svc.obtener(s.id).subscribe((full) => {
      this.creando.set(false); this.editId.set(full.id);
      this.fServ = {
        nombre: full.nombre, descripcion: full.descripcion ?? '',
        objetivo_ms: full.objetivo_ms, impacto_negocio: full.impacto_negocio ?? '', activo: full.activo,
        componentes: (full.componentes ?? []).map((c) => ({
          nombre: c.nombre, tipo: c.tipo, recurso_id: c.recurso_id ?? null, umbral_ms: c.umbral_ms ?? null,
        })),
      };
    });
  }
  cancelar(): void { this.creando.set(false); this.editId.set(null); this.error.set(null); }
  addComp(): void {
    this.fServ.componentes.push({ nombre: '', tipo: 'servicio', recurso_id: null, umbral_ms: null });
  }
  removeComp(i: number): void { this.fServ.componentes.splice(i, 1); }

  guardar(): void {
    const f = this.fServ;
    this.error.set(null);
    if (!f.nombre.trim()) { this.error.set('Indica un nombre.'); return; }
    if (f.componentes.length === 0 || f.componentes.some((c) => !c.nombre.trim())) {
      this.error.set('Cada componente necesita un nombre (al menos uno).'); return;
    }
    const body = {
      nombre: f.nombre, descripcion: f.descripcion || null, objetivo_ms: f.objetivo_ms,
      impacto_negocio: f.impacto_negocio || null, activo: f.activo,
      componentes: f.componentes.map((c) => ({
        nombre: c.nombre, tipo: c.tipo, recurso_id: c.recurso_id || null, umbral_ms: c.umbral_ms || null,
      })),
    };
    const id = this.editId();
    const obs = id ? this.svc.actualizar(id, body) : this.svc.crear(body);
    obs.subscribe({
      next: (s) => { this.cancelar(); this.sel.set(null); this.afterSave(s.id); },
      error: (e) => this.error.set((e as { error?: { message?: string } })?.error?.message ?? 'Error al guardar.'),
    });
  }
  private afterSave(id: number): void {
    this.svc.lista().subscribe((s) => { this.lista.set(s); this.verAnalisis(id); });
  }
  eliminar(): void {
    const s = this.sel();
    if (!s || !confirm(`¿Eliminar la transacción "${s.nombre}"?`)) return;
    this.svc.eliminar(s.id).subscribe({ next: () => { this.sel.set(null); this.cargar(); } });
  }
}
