import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Perfil, ROLES, Rol, Sitio } from '../../core/models';
import { RecursosService } from '../../core/recursos.service';
import { UsuariosService } from '../../core/usuarios.service';

interface FormUsuario {
  email: string;
  nombre: string;
  rol: Rol;
  activo: boolean;
  password: string;
}

@Component({
  selector: 'app-usuarios',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './usuarios.html',
  styleUrl: './usuarios.scss',
})
export class Usuarios implements OnInit {
  private svc = inject(UsuariosService);

  readonly roles = ROLES;
  usuarios = signal<Perfil[]>([]);
  cargando = signal(true);
  error = signal<string | null>(null);
  ok = signal<string | null>(null);

  creando = signal(false);
  editandoId = signal<string | null>(null);
  guardando = signal(false);
  form: FormUsuario = this.vacio();

  ngOnInit(): void {
    this.cargar();
  }

  private cargar(): void {
    this.cargando.set(true);
    this.svc.listar().subscribe({
      next: (p) => { this.usuarios.set(p.data); this.cargando.set(false); },
      error: () => { this.error.set('No se pudieron cargar los usuarios.'); this.cargando.set(false); },
    });
  }

  private vacio(): FormUsuario {
    return { email: '', nombre: '', rol: 'viewer', activo: true, password: '' };
  }

  nuevo(): void {
    this.creando.set(true);
    this.editandoId.set(null);
    this.form = this.vacio();
  }

  editar(u: Perfil): void {
    this.creando.set(false);
    this.editandoId.set(u.id);
    this.form = { email: u.email, nombre: u.nombre ?? '', rol: u.rol, activo: u.activo, password: '' };
  }

  cancelar(): void {
    this.creando.set(false);
    this.editandoId.set(null);
    this.error.set(null);
  }

  guardar(): void {
    this.error.set(null);
    this.ok.set(null);
    const f = this.form;
    this.guardando.set(true);

    const id = this.editandoId();
    if (id) {
      const body: Record<string, unknown> = { email: f.email, nombre: f.nombre, rol: f.rol, activo: f.activo };
      if (f.password.trim()) body['password'] = f.password;
      this.svc.actualizar(id, body).subscribe({
        next: () => { this.guardando.set(false); this.ok.set('Usuario actualizado.'); this.cancelar(); this.cargar(); },
        error: (e) => { this.guardando.set(false); this.error.set(this.msg(e)); },
      });
    } else {
      const body = { email: f.email, nombre: f.nombre, rol: f.rol, activo: f.activo, password: f.password };
      this.svc.crear(body).subscribe({
        next: () => { this.guardando.set(false); this.ok.set('Usuario creado.'); this.cancelar(); this.cargar(); },
        error: (e) => { this.guardando.set(false); this.error.set(this.msg(e)); },
      });
    }
  }

  eliminar(u: Perfil): void {
    if (!confirm(`¿Eliminar al usuario "${u.nombre || u.email}"? Esta acción no se puede deshacer.`)) return;
    this.error.set(null);
    this.ok.set(null);
    this.svc.eliminar(u.id).subscribe({
      next: () => { this.ok.set('Usuario eliminado.'); this.cargar(); },
      error: (e) => this.error.set(this.msg(e)),
    });
  }

  private msg(e: unknown): string {
    const err = e as { error?: { message?: string; errors?: Record<string, string[]> } };
    if (err?.error?.errors) {
      return Object.values(err.error.errors).flat().join(' ');
    }
    return err?.error?.message ?? 'Error al guardar.';
  }

  // ── Alcance por usuario (territoriales que puede ver) ──
  // Es una barrera REAL: la aplica la API. Aqui solo se asigna.
  private recSvc = inject(RecursosService);
  sitios = signal<Sitio[]>([]);
  alcanceDe = signal<string | null>(null);     // usuario con el panel abierto
  alcanceSel = signal<number[]>([]);
  guardandoAlcance = signal(false);

  verAlcance(u: Perfil): void {
    if (this.alcanceDe() === u.id) { this.alcanceDe.set(null); return; }
    this.alcanceDe.set(u.id);
    this.alcanceSel.set([]);
    if (this.sitios().length === 0) {
      this.recSvc.sitios().subscribe((p) => this.sitios.set(p.data));
    }
    this.svc.sitiosDe(u.id).subscribe({ next: (r) => this.alcanceSel.set(r.data) });
  }

  toggleSitio(id: number): void {
    this.alcanceSel.update((s) => s.includes(id) ? s.filter((x) => x !== id) : [...s, id]);
  }

  guardarAlcance(u: Perfil): void {
    this.error.set(null); this.ok.set(null);
    this.guardandoAlcance.set(true);
    this.svc.asignarSitios(u.id, this.alcanceSel()).subscribe({
      next: () => {
        this.guardandoAlcance.set(false);
        this.ok.set(this.alcanceSel().length
          ? `Alcance guardado: ${this.alcanceSel().length} sitio(s).`
          : 'Alcance quitado: vera toda la entidad.');
      },
      error: (e) => {
        this.guardandoAlcance.set(false);
        this.error.set((e as { error?: { message?: string } })?.error?.message ?? 'No se pudo guardar el alcance.');
      },
    });
  }
}
