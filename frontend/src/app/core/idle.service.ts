import { Injectable, inject } from '@angular/core';
import { Router } from '@angular/router';
import { environment } from '../../environments/environment';
import { AuthService } from './auth.service';

/** Cierra la sesión tras N minutos de inactividad (seguridad / cumplimiento). */
@Injectable({ providedIn: 'root' })
export class IdleService {
  private auth = inject(AuthService);
  private router = inject(Router);

  private readonly eventos = ['mousemove', 'keydown', 'click', 'scroll', 'touchstart'];
  private readonly ms = (environment.idleMinutes ?? 30) * 60_000;
  private timer: ReturnType<typeof setTimeout> | undefined;
  private readonly onActividad = () => this.reiniciar();

  iniciar(): void {
    if (!this.ms || this.ms <= 0) return;
    this.eventos.forEach((e) => document.addEventListener(e, this.onActividad, { passive: true }));
    this.reiniciar();
  }

  detener(): void {
    this.eventos.forEach((e) => document.removeEventListener(e, this.onActividad));
    if (this.timer) clearTimeout(this.timer);
  }

  private reiniciar(): void {
    if (this.timer) clearTimeout(this.timer);
    this.timer = setTimeout(() => this.expirar(), this.ms);
  }

  private async expirar(): Promise<void> {
    this.detener();
    await this.auth.cerrarSesion();
    await this.router.navigate(['/login'], { queryParams: { motivo: 'inactividad' } });
  }
}
