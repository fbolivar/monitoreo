import { Injectable, computed, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { ApiService } from './api.service';
import { Perfil, Rol } from './models';

/** Autenticación LOCAL contra la API (sin Supabase). El login devuelve un JWT
 *  propio que se guarda en localStorage y adjunta el authInterceptor. */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private api = inject(ApiService);
  private readonly TOKEN_KEY = 'monitoreo_token';

  readonly token = signal<string | null>(localStorage.getItem(this.TOKEN_KEY));
  readonly perfil = signal<Perfil | null>(null);
  readonly cargando = signal(true);

  readonly accessToken = computed(() => this.token());
  readonly autenticado = computed(() => !!this.token() && !!this.perfil());
  readonly rol = computed<Rol | null>(() => this.perfil()?.rol ?? null);
  /** viewer = solo lectura; admin/operador pueden editar. */
  readonly puedeEditar = computed(() => this.rol() === 'admin' || this.rol() === 'operador');
  readonly esAdmin = computed(() => this.rol() === 'admin');

  /** Llamado una vez al arrancar: si hay token, valida cargando el perfil. */
  async init(): Promise<void> {
    if (this.token()) {
      try {
        this.perfil.set(await firstValueFrom(this.api.get<Perfil>('/me')));
      } catch (e) {
        const status = (e as { status?: number })?.status;
        // Solo cerrar sesión si el token es inválido; ante fallo de red/5xx
        // transitorio conservar el token (no expulsar por un blip).
        if (status === 401 || status === 403) {
          this.limpiar();
        } else {
          this.perfil.set(null);
        }
      }
    }
    this.cargando.set(false);
  }

  /** Devuelve 'ok' si inició sesión, o '2fa' si se requiere código (con mensaje opcional). */
  async iniciarSesion(email: string, password: string, codigo?: string):
    Promise<{ estado: 'ok' | '2fa'; mensaje?: string }> {
    const r = await firstValueFrom(
      this.api.post<{ token?: string; perfil?: Perfil; requiere_2fa?: boolean; mensaje?: string }>(
        '/auth/login', { email, password, codigo },
      ),
    );
    if (r.requiere_2fa) {
      return { estado: '2fa', mensaje: r.mensaje };
    }
    localStorage.setItem(this.TOKEN_KEY, r.token!);
    this.token.set(r.token!);
    this.perfil.set(r.perfil!);
    return { estado: 'ok' };
  }

  // ── 2FA (TOTP) del usuario actual ─────────────────────────────────
  async iniciar2fa(): Promise<{ secret: string; uri: string }> {
    return firstValueFrom(this.api.post<{ secret: string; uri: string }>('/2fa/iniciar', {}));
  }
  async activar2fa(codigo: string): Promise<void> {
    await firstValueFrom(this.api.post('/2fa/activar', { codigo }));
    await this.refrescarPerfil();
  }
  async desactivar2fa(codigo: string): Promise<void> {
    await firstValueFrom(this.api.post('/2fa/desactivar', { codigo }));
    await this.refrescarPerfil();
  }
  private async refrescarPerfil(): Promise<void> {
    try { this.perfil.set(await firstValueFrom(this.api.get<Perfil>('/me'))); } catch { /* ignore */ }
  }

  async cerrarSesion(): Promise<void> {
    this.limpiar();
  }

  private limpiar(): void {
    localStorage.removeItem(this.TOKEN_KEY);
    this.token.set(null);
    this.perfil.set(null);
  }
}
