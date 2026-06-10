import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../core/auth.service';
import { Recurso, Sitio, TipoRecurso } from '../../core/models';
import { RecursosService } from '../../core/recursos.service';
import { EstadoBadge } from '../../shared/estado-badge';

interface FormRecurso {
  nombre: string;
  tipo_id: number | null;
  sitio_id: number | null;
  hostname: string;
  intervalo_segundos: number;
  activo: boolean;
  parametrosTexto: string;
  secretosTexto: string;
}

@Component({
  selector: 'app-recursos',
  standalone: true,
  imports: [FormsModule, RouterLink, EstadoBadge],
  templateUrl: './recursos.html',
  styleUrl: './recursos.scss',
})
export class Recursos implements OnInit {
  private svc = inject(RecursosService);
  auth = inject(AuthService);

  recursos = signal<Recurso[]>([]);
  tipos = signal<TipoRecurso[]>([]);
  sitios = signal<Sitio[]>([]);
  cargando = signal(true);
  error = signal<string | null>(null);

  fTipo = signal<number | ''>('');
  fSitio = signal<number | ''>('');
  busqueda = signal('');

  editandoId = signal<number | null>(null); // null = ninguno
  creando = signal(false);
  guardando = signal(false);
  form: FormRecurso = this.vacio();

  filtrados = computed(() => {
    const t = this.fTipo();
    const s = this.fSitio();
    const q = this.busqueda().trim().toLowerCase();
    return this.recursos().filter((r) => {
      if (t && r.tipo_id !== t) return false;
      if (s && r.sitio_id !== s) return false;
      if (q && !`${r.nombre} ${r.hostname ?? ''}`.toLowerCase().includes(q)) return false;
      return true;
    });
  });

  ngOnInit(): void {
    this.cargar();
    this.svc.tipos().subscribe((p) => this.tipos.set(p.data));
    this.svc.sitios().subscribe((p) => this.sitios.set(p.data));
  }

  private cargar(): void {
    this.cargando.set(true);
    this.svc.listar().subscribe({
      next: (p) => { this.recursos.set(p.data); this.cargando.set(false); },
      error: () => { this.error.set('No se pudieron cargar los recursos.'); this.cargando.set(false); },
    });
  }

  private vacio(): FormRecurso {
    return {
      nombre: '', tipo_id: null, sitio_id: null, hostname: '',
      intervalo_segundos: 60, activo: true, parametrosTexto: '{}', secretosTexto: '',
    };
  }

  nuevo(): void {
    this.creando.set(true);
    this.editandoId.set(null);
    this.form = this.vacio();
  }

  editar(r: Recurso): void {
    this.creando.set(false);
    this.editandoId.set(r.id);
    this.form = {
      nombre: r.nombre,
      tipo_id: r.tipo_id,
      sitio_id: r.sitio_id ?? null,
      hostname: r.hostname ?? '',
      intervalo_segundos: r.intervalo_segundos,
      activo: r.activo,
      parametrosTexto: JSON.stringify(r.parametros ?? {}, null, 2),
      secretosTexto: '',
    };
  }

  cancelar(): void {
    this.creando.set(false);
    this.editandoId.set(null);
    this.error.set(null);
  }

  guardar(): void {
    const f = this.form;
    this.error.set(null);

    let parametros: Record<string, unknown> = {};
    try { parametros = f.parametrosTexto.trim() ? JSON.parse(f.parametrosTexto) : {}; }
    catch { this.error.set('Parámetros: JSON inválido.'); return; }

    const body: Record<string, unknown> = {
      nombre: f.nombre,
      tipo_id: f.tipo_id,
      sitio_id: f.sitio_id,
      hostname: f.hostname || null,
      intervalo_segundos: f.intervalo_segundos,
      activo: f.activo,
      parametros,
    };

    if (f.secretosTexto.trim()) {
      try { body['secretos'] = JSON.parse(f.secretosTexto); }
      catch { this.error.set('Secretos: JSON inválido.'); return; }
    }

    this.guardando.set(true);
    const id = this.editandoId();
    const obs = id ? this.svc.actualizar(id, body) : this.svc.crear(body);
    obs.subscribe({
      next: () => { this.guardando.set(false); this.cancelar(); this.cargar(); },
      error: (e) => { this.guardando.set(false); this.error.set(this.msg(e)); },
    });
  }

  eliminar(r: Recurso): void {
    if (!confirm(`¿Eliminar el recurso "${r.nombre}"? Esta acción no se puede deshacer.`)) return;
    this.svc.eliminar(r.id).subscribe({
      next: () => this.cargar(),
      error: (e) => this.error.set(this.msg(e)),
    });
  }

  private msg(e: unknown): string {
    const err = e as { error?: { message?: string } };
    return err?.error?.message ?? 'Error al guardar.';
  }
}
