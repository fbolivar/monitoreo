import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../../core/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [FormsModule],
  template: `
    <div class="wrap">
      <form class="card box" (ngSubmit)="entrar()">
        <h1>Monitoreo TI</h1>
        <p class="text-dim">Acceso al panel de operación</p>

        <label>Correo</label>
        <input type="email" name="email" [(ngModel)]="email" autocomplete="username" required />

        <label>Contraseña</label>
        <input type="password" name="password" [(ngModel)]="password"
               autocomplete="current-password" required />

        @if (error()) { <div class="err">{{ error() }}</div> }

        <button class="btn btn-primary" type="submit" [disabled]="cargando()">
          {{ cargando() ? 'Entrando…' : 'Entrar' }}
        </button>
      </form>
    </div>
  `,
  styles: [
    `
      .wrap { display: grid; place-items: center; min-height: 100vh; }
      .box { display: flex; flex-direction: column; gap: 8px; width: 320px; padding: 24px; }
      h1 { margin: 0; font-size: 20px; }
      label { color: var(--text-dim); font-size: 12px; margin-top: 6px; }
      .err { color: var(--sev-critical); font-size: 12px; }
      button { margin-top: 14px; }
    `,
  ],
})
export class Login {
  private auth = inject(AuthService);
  private router = inject(Router);

  email = '';
  password = '';
  cargando = signal(false);
  error = signal<string | null>(null);

  async entrar(): Promise<void> {
    this.error.set(null);
    this.cargando.set(true);
    try {
      await this.auth.iniciarSesion(this.email, this.password);
      await this.router.navigate(['/']);
    } catch (e: unknown) {
      this.error.set(e instanceof Error ? e.message : 'No se pudo iniciar sesión');
    } finally {
      this.cargando.set(false);
    }
  }
}
