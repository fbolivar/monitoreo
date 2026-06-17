import { Component, OnDestroy, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../core/auth.service';
import { DescubrimientoService } from '../../core/descubrimiento.service';
import {
  CandidatoEstado,
  DescubrimientoCandidato,
  DescubrimientoEscaneo,
  Sitio,
  TipoRecurso,
} from '../../core/models';
import { SitiosService } from '../../core/sitios.service';
import { fecha, hace } from '../../shared/tiempo';

interface AltaForm {
  tipo_id: number | null;
  nombre: string;
  sitio_id: number | null;
  intervalo_segundos: number | null;
  snmp_community: string;
}

@Component({
  selector: 'app-descubrimiento',
  standalone: true,
  imports: [FormsModule, RouterLink],
  templateUrl: './descubrimiento.html',
  styleUrl: './descubrimiento.scss',
})
export class Descubrimiento implements OnInit, OnDestroy {
  private svc = inject(DescubrimientoService);
  private sitiosSvc = inject(SitiosService);
  auth = inject(AuthService);

  fecha = fecha;
  hace = hace;

  escaneos = signal<DescubrimientoEscaneo[]>([]);
  seleccion = signal<DescubrimientoEscaneo | null>(null);
  tipos = signal<TipoRecurso[]>([]);
  sitios = signal<Sitio[]>([]);
  cargando = signal(true);
  error = signal<string | null>(null);

  // Formulario de barrido.
  subred = signal('');
  snmpVersion = signal('2c');
  snmpCommunity = signal('');
  lanzando = signal(false);

  // Alta de candidato (inline).
  altaId = signal<number | null>(null);
  alta = signal<AltaForm>(this.altaVacia());
  guardando = signal(false);

  private poll?: ReturnType<typeof setInterval>;

  candidatos = computed(() => this.seleccion()?.candidatos ?? []);
  nuevos = computed(() => this.candidatos().filter((c) => c.estado === 'nuevo'));

  ngOnInit(): void {
    this.cargar();
    this.svc.tipos().subscribe((t) => this.tipos.set(t));
    this.sitiosSvc.listar().subscribe((p) => this.sitios.set(p.data));
    // Refresca mientras haya un escaneo en curso.
    this.poll = setInterval(() => this.refrescarSiActivo(), 4000);
  }

  ngOnDestroy(): void {
    if (this.poll) clearInterval(this.poll);
  }

  cargar(): void {
    this.cargando.set(true);
    this.svc.listar().subscribe({
      next: (p) => {
        this.escaneos.set(p.data);
        this.cargando.set(false);
        if (!this.seleccion() && p.data.length) this.seleccionar(p.data[0]);
      },
      error: () => this.cargando.set(false),
    });
  }

  private refrescarSiActivo(): void {
    const activo = this.escaneos().some((e) => e.estado === 'pendiente' || e.estado === 'ejecutando');
    if (activo) {
      this.svc.listar().subscribe((p) => this.escaneos.set(p.data));
      const sel = this.seleccion();
      if (sel && (sel.estado === 'pendiente' || sel.estado === 'ejecutando')) {
        this.svc.detalle(sel.id).subscribe((d) => this.seleccion.set(d));
      }
    }
  }

  seleccionar(e: DescubrimientoEscaneo): void {
    this.altaId.set(null);
    this.svc.detalle(e.id).subscribe((d) => this.seleccion.set(d));
  }

  lanzar(): void {
    const subred = this.subred().trim();
    if (!subred) return;
    this.lanzando.set(true);
    this.error.set(null);
    this.svc
      .escanear({
        subred,
        snmp_version: this.snmpVersion(),
        snmp_community: this.snmpCommunity() || undefined,
      })
      .subscribe({
        next: () => {
          this.subred.set('');
          this.snmpCommunity.set('');
          this.lanzando.set(false);
          this.cargar();
        },
        error: (e) => {
          this.error.set(e?.error?.message ?? 'No se pudo encolar el barrido.');
          this.lanzando.set(false);
        },
      });
  }

  eliminar(e: DescubrimientoEscaneo, ev: Event): void {
    ev.stopPropagation();
    if (!confirm(`¿Eliminar el barrido de ${e.subred} y sus candidatos?`)) return;
    this.svc.eliminar(e.id).subscribe(() => {
      if (this.seleccion()?.id === e.id) this.seleccion.set(null);
      this.cargar();
    });
  }

  // ── Alta de candidato ──────────────────────────────────────────────
  abrirAlta(c: DescubrimientoCandidato): void {
    const tipo = this.tipos().find((t) => t.codigo === c.tipo_sugerido);
    this.alta.set({
      ...this.altaVacia(),
      tipo_id: tipo?.id ?? null,
      nombre: c.sysname || c.ip,
    });
    this.altaId.set(c.id);
  }

  cancelarAlta(): void {
    this.altaId.set(null);
  }

  setAlta<K extends keyof AltaForm>(campo: K, valor: AltaForm[K]): void {
    this.alta.set({ ...this.alta(), [campo]: valor });
  }

  confirmarAlta(c: DescubrimientoCandidato): void {
    const f = this.alta();
    if (!f.tipo_id || !f.nombre.trim()) return;
    this.guardando.set(true);
    const secretos = f.snmp_community ? { snmp_community: f.snmp_community } : undefined;
    this.svc
      .agregar(c.id, {
        tipo_id: f.tipo_id,
        nombre: f.nombre.trim(),
        sitio_id: f.sitio_id || undefined,
        intervalo_segundos: f.intervalo_segundos || undefined,
        secretos,
      })
      .subscribe({
        next: () => {
          this.guardando.set(false);
          this.altaId.set(null);
          this.recargarDetalle();
        },
        error: (e) => {
          this.guardando.set(false);
          alert(e?.error?.message ?? 'No se pudo dar de alta el recurso.');
        },
      });
  }

  descartar(c: DescubrimientoCandidato): void {
    this.svc.descartar(c.id).subscribe(() => this.recargarDetalle());
  }

  private recargarDetalle(): void {
    const sel = this.seleccion();
    if (sel) this.svc.detalle(sel.id).subscribe((d) => this.seleccion.set(d));
    this.svc.listar().subscribe((p) => this.escaneos.set(p.data));
  }

  private altaVacia(): AltaForm {
    return { tipo_id: null, nombre: '', sitio_id: null, intervalo_segundos: null, snmp_community: '' };
  }

  estadoLabel(e: CandidatoEstado): string {
    return { nuevo: 'Nuevo', agregado: 'Agregado', descartado: 'Descartado', existente: 'Ya existe' }[e];
  }
}
