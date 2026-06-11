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
        <img src="logo-simon.png" alt="Parques Nacionales Naturales de Colombia" class="logo" />
        <h1>SIMON</h1>
        <p class="sub">Sistema Integral de Monitoreo</p>

        <label>Correo</label>
        <input type="email" name="email" [(ngModel)]="email" autocomplete="username" required />

        <label>Contraseña</label>
        <input type="password" name="password" [(ngModel)]="password"
               autocomplete="current-password" required />

        @if (error()) { <div class="err">{{ error() }}</div> }

        <button class="btn btn-primary" type="submit" [disabled]="cargando()">
          {{ cargando() ? 'Entrando…' : 'Ingresar' }}
        </button>

        <p class="pie text-dim">Parques Nacionales Naturales de Colombia</p>
      </form>
    </div>
  `,
  styles: [
    `
      .wrap {
        display: grid; place-items: center; min-height: 100vh;
        background: linear-gradient(160deg, #eef4ef 0%, #dceadf 100%);
      }
      .box { display: flex; flex-direction: column; gap: 8px; width: 360px; padding: 32px 28px; }
      .logo { width: 190px; align-self: center; margin-bottom: 8px; }
      h1 { margin: 0; font-size: 30px; text-align: center; color: var(--primary-dark); letter-spacing: .04em; }
      .sub { margin: 0 0 14px; text-align: center; color: var(--text-dim); }
      label { color: var(--text-dim); font-size: 12px; margin-top: 6px; }
      .err { color: var(--sev-critical); font-size: 12.5px; }
      button { margin-top: 16px; padding: 10px; font-weight: 600; }
      .pie { text-align: center; font-size: 11px; margin: 16px 0 0; }
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
