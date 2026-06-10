import { Injectable, computed, inject, signal } from '@angular/core';
import { Session } from '@supabase/supabase-js';
import { firstValueFrom } from 'rxjs';
import { ApiService } from './api.service';
import { Perfil, Rol } from './models';
import { SupabaseService } from './supabase.client';

/** Sesión + perfil/rol del usuario. El rol de aplicación (admin/operador/viewer)
 *  se obtiene de la API (/me), no del JWT. */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private supabase = inject(SupabaseService).client;
  private api = inject(ApiService);

  readonly session = signal<Session | null>(null);
  readonly perfil = signal<Perfil | null>(null);
  readonly cargando = signal(true);

  readonly accessToken = computed(() => this.session()?.access_token ?? null);
  readonly autenticado = computed(() => !!this.session());
  readonly rol = computed<Rol | null>(() => this.perfil()?.rol ?? null);
  /** viewer = solo lectura; admin/operador pueden editar configuración. */
  readonly puedeEditar = computed(() => this.rol() === 'admin' || this.rol() === 'operador');
  readonly esAdmin = computed(() => this.rol() === 'admin');

  /** Llamado una vez al arrancar la app. */
  async init(): Promise<void> {
    const { data } = await this.supabase.auth.getSession();
    await this.aplicarSesion(data.session);

    this.supabase.auth.onAuthStateChange((_evt, session) => {
      void this.aplicarSesion(session);
    });
    this.cargando.set(false);
  }

  private async aplicarSesion(session: Session | null): Promise<void> {
    this.session.set(session);
    if (session) {
      await this.cargarPerfil();
    } else {
      this.perfil.set(null);
    }
  }

  private async cargarPerfil(): Promise<void> {
    try {
      const perfil = await firstValueFrom(this.api.get<Perfil>('/me'));
      this.perfil.set(perfil);
    } catch {
      this.perfil.set(null);
    }
  }

  async iniciarSesion(email: string, password: string): Promise<void> {
    const { error } = await this.supabase.auth.signInWithPassword({ email, password });
    if (error) throw error;
  }

  async cerrarSesion(): Promise<void> {
    await this.supabase.auth.signOut();
    this.session.set(null);
    this.perfil.set(null);
  }
}
