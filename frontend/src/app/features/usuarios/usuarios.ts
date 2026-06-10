import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Perfil, ROLES, Rol } from '../../core/models';
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

  private msg(e: unknown): string {
    const err = e as { error?: { message?: string; errors?: Record<string, string[]> } };
    if (err?.error?.errors) {
      return Object.values(err.error.errors).flat().join(' ');
    }
    return err?.error?.message ?? 'Error al guardar.';
  }
}
