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
      } catch {
        this.limpiar();
      }
    }
    this.cargando.set(false);
  }

  async iniciarSesion(email: string, password: string): Promise<void> {
    const r = await firstValueFrom(
      this.api.post<{ token: string; perfil: Perfil }>('/auth/login', { email, password }),
    );
    localStorage.setItem(this.TOKEN_KEY, r.token);
    this.token.set(r.token);
    this.perfil.set(r.perfil);
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
