import { Injectable, inject } from '@angular/core';
import { RealtimeChannel } from '@supabase/supabase-js';
import { Incidencia, Recurso } from './models';
import { SupabaseService } from './supabase.client';

/** Suscripciones a Supabase Realtime para refrescar estado en vivo.
 *  Requiere que las tablas `recursos` e `incidencias` estén en la publicación
 *  de Realtime de Supabase (Database -> Replication). */
@Injectable({ providedIn: 'root' })
export class RealtimeService {
  private supabase = inject(SupabaseService).client;

  /** Cambios de estado de recursos. Devuelve función para desuscribir. */
  onRecursos(cb: (r: Recurso) => void): () => void {
    const ch: RealtimeChannel = this.supabase
      .channel('rt-recursos')
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'recursos' },
        (payload) => cb(payload.new as Recurso),
      )
      .subscribe();
    return () => void this.supabase.removeChannel(ch);
  }

  /** Altas/cambios de incidencias. */
  onIncidencias(cb: (i: Incidencia) => void): () => void {
    const ch: RealtimeChannel = this.supabase
      .channel('rt-incidencias')
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'incidencias' },
        (payload) => cb(payload.new as Incidencia),
      )
      .subscribe();
    return () => void this.supabase.removeChannel(ch);
  }
}
