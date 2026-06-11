import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../../core/auth.service';

@Component({
  selector: 'app-seguridad',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './seguridad.html',
  styleUrl: './seguridad.scss',
})
export class Seguridad {
  auth = inject(AuthService);

  paso = signal<'inicio' | 'enrolando'>('inicio');
  secret = signal('');
  uri = signal('');
  codigo = '';
  error = signal<string | null>(null);
  ok = signal<string | null>(null);
  cargando = signal(false);

  async iniciar(): Promise<void> {
    this.error.set(null); this.ok.set(null); this.cargando.set(true);
    try {
      const r = await this.auth.iniciar2fa();
      this.secret.set(r.secret); this.uri.set(r.uri); this.paso.set('enrolando');
    } catch (e) { this.error.set(this.msg(e)); } finally { this.cargando.set(false); }
  }

  async activar(): Promise<void> {
    this.error.set(null); this.cargando.set(true);
    try {
      await this.auth.activar2fa(this.codigo);
      this.ok.set('2FA activado correctamente.'); this.paso.set('inicio'); this.codigo = '';
    } catch (e) { this.error.set(this.msg(e)); } finally { this.cargando.set(false); }
  }

  async desactivar(): Promise<void> {
    this.error.set(null); this.ok.set(null); this.cargando.set(true);
    try {
      await this.auth.desactivar2fa(this.codigo);
      this.ok.set('2FA desactivado.'); this.codigo = '';
    } catch (e) { this.error.set(this.msg(e)); } finally { this.cargando.set(false); }
  }

  private msg(e: unknown): string {
    return (e as { error?: { message?: string } })?.error?.message ?? 'Error.';
  }
}
