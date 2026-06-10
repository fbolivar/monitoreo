import { Component, inject } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { AuthService } from '../core/auth.service';

/** Marco principal: barra lateral de navegación + topbar. */
@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    <div class="layout">
      <aside class="side">
        <div class="brand">◎ Monitoreo TI</div>
        <nav>
          <a routerLink="/" routerLinkActive="active" [routerLinkActiveOptions]="{ exact: true }">Dashboard</a>
          <a routerLink="/recursos" routerLinkActive="active">Recursos</a>
          <a routerLink="/incidencias" routerLinkActive="active">Incidencias</a>
          <a routerLink="/configuracion" routerLinkActive="active">Configuración</a>
        </nav>
      </aside>

      <div class="main">
        <header class="topbar">
          <div class="spacer"></div>
          <div class="user">
            <span class="text-dim">{{ auth.perfil()?.email }}</span>
            <span class="rol">{{ auth.rol() }}</span>
            <button class="btn" (click)="salir()">Salir</button>
          </div>
        </header>
        <main class="content">
          <router-outlet />
        </main>
      </div>
    </div>
  `,
  styles: [
    `
      .layout { display: grid; grid-template-columns: 210px 1fr; min-height: 100vh; }
      .side { background: var(--bg-1); border-right: 1px solid var(--border); padding: 14px 10px; }
      .brand { font-weight: 700; padding: 6px 8px 16px; }
      nav { display: flex; flex-direction: column; gap: 2px; }
      nav a { color: var(--text-dim); padding: 8px 10px; border-radius: var(--radius); }
      nav a:hover { background: var(--bg-2); color: var(--text); text-decoration: none; }
      nav a.active { background: var(--bg-3); color: var(--text); }
      .main { display: flex; flex-direction: column; min-width: 0; }
      .topbar { display: flex; align-items: center; height: 46px; padding: 0 16px;
                border-bottom: 1px solid var(--border); background: var(--bg-1); }
      .spacer { flex: 1; }
      .user { display: flex; align-items: center; gap: 10px; }
      .rol { background: var(--bg-3); border: 1px solid var(--border); border-radius: 10px;
             padding: 1px 8px; font-size: 11px; text-transform: uppercase; }
      .content { padding: 16px; min-width: 0; }
    `,
  ],
})
export class Shell {
  auth = inject(AuthService);
  private router = inject(Router);

  async salir(): Promise<void> {
    await this.auth.cerrarSesion();
    await this.router.navigate(['/login']);
  }
}
