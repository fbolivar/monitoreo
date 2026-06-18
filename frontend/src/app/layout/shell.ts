import { Component, OnDestroy, OnInit, inject } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { AuthService } from '../core/auth.service';
import { IdleService } from '../core/idle.service';
import { PushService } from '../core/push.service';

/** Marco principal: barra lateral institucional + topbar. */
@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    <div class="layout">
      <aside class="side">
        <div class="brand">
          <img src="logo-simon.png" alt="Parques Nacionales Naturales de Colombia" class="logo" />
          <div class="marca">
            <b>SIMON</b>
            <span>Sistema Integral de Monitoreo</span>
          </div>
        </div>
        <nav>
          <a routerLink="/" routerLinkActive="active" [routerLinkActiveOptions]="{ exact: true }">Dashboard</a>
          <a routerLink="/recursos" routerLinkActive="active">Recursos</a>
          @if (auth.puedeEditar()) {
            <a routerLink="/descubrimiento" routerLinkActive="active">Descubrimiento</a>
          }
          <a routerLink="/sitios" routerLinkActive="active">Sitios</a>
          <a routerLink="/topologia" routerLinkActive="active">Topología</a>
          <a routerLink="/flujos" routerLinkActive="active">Flujos</a>
          <a routerLink="/servicios" routerLinkActive="active">Servicios</a>
          <a routerLink="/incidencias" routerLinkActive="active">Incidencias</a>
          <a routerLink="/correlaciones" routerLinkActive="active">Correlaciones</a>
          <a routerLink="/traps" routerLinkActive="active">Traps</a>
          <a routerLink="/rum" routerLinkActive="active">Experiencia (RUM)</a>
          <a routerLink="/reportes" routerLinkActive="active">Reportes</a>
          <a routerLink="/cumplimiento" routerLinkActive="active">Cumplimiento</a>
          @if (auth.puedeEditar()) {
            <a routerLink="/runbooks" routerLinkActive="active">Runbooks</a>
          }
          <a routerLink="/wallboard">Tablero NOC ↗</a>
          <a routerLink="/status">Estado público ↗</a>
          <a routerLink="/configuracion" routerLinkActive="active">Configuración</a>
          @if (auth.esAdmin()) {
            <a routerLink="/agentes" routerLinkActive="active">Agentes</a>
            <a routerLink="/usuarios" routerLinkActive="active">Usuarios</a>
            <a routerLink="/auditoria" routerLinkActive="active">Auditoría</a>
          }
        </nav>
        <div class="pie text-dim">Parques Nacionales Naturales<br />de Colombia</div>
      </aside>

      <div class="main">
        <header class="topbar">
          <div class="spacer"></div>
          <div class="user">
            <span class="text-dim">{{ auth.perfil()?.email }}</span>
            <span class="rol">{{ auth.rol() }}</span>
            @if (push.soportado) {
              <button class="btn" title="Activar notificaciones push" (click)="activarPush()">🔔</button>
            }
            <a routerLink="/seguridad" class="btn">Seguridad</a>
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
      .layout { display: grid; grid-template-columns: 230px 1fr; min-height: 100vh; }

      .side {
        background: #fff;
        border-right: 1px solid var(--border);
        padding: 16px 12px;
        display: flex;
        flex-direction: column;
      }
      .brand { display: flex; flex-direction: column; gap: 10px; padding: 6px 6px 14px; border-bottom: 1px solid var(--border); }
      .brand .logo { width: 100%; max-width: 170px; height: auto; }
      .marca { display: flex; flex-direction: column; line-height: 1.1; }
      .marca b { font-size: 20px; color: var(--primary-dark); letter-spacing: .02em; }
      .marca span { font-size: 11px; color: var(--text-dim); }

      nav { display: flex; flex-direction: column; gap: 3px; margin-top: 14px; }
      nav a {
        color: var(--text); padding: 9px 12px; border-radius: var(--radius);
        border-left: 3px solid transparent; font-weight: 500;
      }
      nav a:hover { background: var(--bg-2); text-decoration: none; }
      nav a.active { background: var(--primary-50); color: var(--primary-dark); border-left-color: var(--primary); font-weight: 600; }

      .pie { margin-top: auto; padding: 12px 8px 4px; font-size: 11px; }

      .main { display: flex; flex-direction: column; min-width: 0; }
      .topbar {
        display: flex; align-items: center; height: 52px; padding: 0 20px;
        border-bottom: 1px solid var(--border); background: #fff;
        border-top: 3px solid var(--primary);
      }
      .spacer { flex: 1; }
      .user { display: flex; align-items: center; gap: 12px; }
      .rol {
        background: var(--primary-50); color: var(--primary-dark);
        border: 1px solid #cfe3d4; border-radius: 10px;
        padding: 2px 10px; font-size: 11px; font-weight: 600; text-transform: uppercase;
      }
      .content { padding: 20px; min-width: 0; }
    `,
  ],
})
export class Shell implements OnInit, OnDestroy {
  auth = inject(AuthService);
  push = inject(PushService);
  private router = inject(Router);
  private idle = inject(IdleService);

  async activarPush(): Promise<void> {
    alert(await this.push.activar());
  }

  ngOnInit(): void {
    this.idle.iniciar();
  }

  ngOnDestroy(): void {
    this.idle.detener();
  }

  async salir(): Promise<void> {
    this.idle.detener();
    await this.auth.cerrarSesion();
    await this.router.navigate(['/login']);
  }
}
