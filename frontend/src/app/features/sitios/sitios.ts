import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../../core/auth.service';
import { Sitio } from '../../core/models';
import { SitiosService } from '../../core/sitios.service';

interface FormSitio {
  codigo: string;
  nombre: string;
  ciudad: string;
  direccion: string;
  latitud: number | null;
  longitud: number | null;
  descripcion: string;
  activo: boolean;
}

@Component({
  selector: 'app-sitios',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './sitios.html',
  styleUrl: './sitios.scss',
})
export class Sitios implements OnInit {
  private svc = inject(SitiosService);
  auth = inject(AuthService);

  sitios = signal<Sitio[]>([]);
  cargando = signal(true);
  error = signal<string | null>(null);
  ok = signal<string | null>(null);

  creando = signal(false);
  editandoId = signal<number | null>(null);
  guardando = signal(false);
  form: FormSitio = this.vacio();

  ngOnInit(): void {
    this.cargar();
  }

  private cargar(): void {
    this.cargando.set(true);
    this.svc.listar().subscribe({
      next: (p) => { this.sitios.set(p.data); this.cargando.set(false); },
      error: () => { this.error.set('No se pudieron cargar los sitios.'); this.cargando.set(false); },
    });
  }

  private vacio(): FormSitio {
    return { codigo: '', nombre: '', ciudad: '', direccion: '', latitud: null, longitud: null, descripcion: '', activo: true };
  }

  nuevo(): void {
    this.creando.set(true);
    this.editandoId.set(null);
    this.error.set(null);
    this.ok.set(null);
    this.form = this.vacio();
  }

  editar(s: Sitio): void {
    this.creando.set(false);
    this.editandoId.set(s.id);
    this.error.set(null);
    this.ok.set(null);
    this.form = {
      codigo: s.codigo,
      nombre: s.nombre,
      ciudad: s.ciudad ?? '',
      direccion: s.direccion ?? '',
      latitud: s.latitud ?? null,
      longitud: s.longitud ?? null,
      descripcion: s.descripcion ?? '',
      activo: s.activo ?? true,
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
    if (!f.codigo.trim() || !f.nombre.trim()) {
      this.error.set('Código y nombre son obligatorios.');
      return;
    }

    const body: Partial<Sitio> = {
      codigo: f.codigo,
      nombre: f.nombre,
      ciudad: f.ciudad || null,
      direccion: f.direccion || null,
      latitud: f.latitud,
      longitud: f.longitud,
      descripcion: f.descripcion || null,
      activo: f.activo,
    };

    this.guardando.set(true);
    const id = this.editandoId();
    const obs = id ? this.svc.actualizar(id, body) : this.svc.crear(body);
    obs.subscribe({
      next: () => {
        this.guardando.set(false);
        this.ok.set(id ? 'Sitio actualizado.' : 'Sitio creado.');
        this.cancelar();
        this.cargar();
      },
      error: (e) => { this.guardando.set(false); this.error.set(this.msg(e)); },
    });
  }

  eliminar(s: Sitio): void {
    if (!confirm(`¿Eliminar el sitio "${s.nombre}"? Los recursos asociados quedarán sin sitio.`)) return;
    this.svc.eliminar(s.id).subscribe({
      next: () => { this.ok.set('Sitio eliminado.'); this.cargar(); },
      error: (e) => this.error.set(this.msg(e)),
    });
  }

  private msg(e: unknown): string {
    const err = e as { error?: { message?: string; errors?: Record<string, string[]> } };
    if (err?.error?.errors) return Object.values(err.error.errors).flat().join(' ');
    return err?.error?.message ?? 'Error al guardar.';
  }
}
