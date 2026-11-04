import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Canal, NivelEscalado, Perfil, PoliticaEscalado, Severidad, TurnoOncall } from '../../core/models';
import { OncallService } from '../../core/oncall.service';
import { UsuariosService } from '../../core/usuarios.service';
import { ConfigService } from '../../core/config.service';
import { fecha } from '../../shared/tiempo';

/**
 * Guardias (on-call) + políticas de escalado multinivel. Admin.
 * Define quién está de guardia (rotación) y qué se hace si una alarma no se
 * reconoce a tiempo (niveles → canal / turno de guardia / usuario).
 */
@Component({
  selector: 'app-guardias',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './guardias.html',
  styleUrl: './guardias.scss',
})
export class Guardias implements OnInit {
  private svc = inject(OncallService);
  private usuariosSvc = inject(UsuariosService);
  private configSvc = inject(ConfigService);
  fecha = fecha;

  turnos = signal<TurnoOncall[]>([]);
  politicas = signal<PoliticaEscalado[]>([]);
  usuarios = signal<Perfil[]>([]);
  canales = signal<Canal[]>([]);
  error = signal<string | null>(null);

  // ── Editor de turno ──
  turnoEdit = signal<TurnoOncall | null>(null);
  nuevoPerfil = signal<string>('');

  // ── Editor de política ──
  polEdit = signal<PoliticaEscalado | null>(null);

  ngOnInit(): void {
    this.cargar();
    this.usuariosSvc.listar().subscribe((p) => this.usuarios.set(p.data.filter((u) => u.activo)));
    this.configSvc.canales().subscribe((p) => this.canales.set(p.data));
  }
  private cargar(): void {
    this.svc.turnos().subscribe((r) => this.turnos.set(r.data));
    this.svc.politicas().subscribe((r) => this.politicas.set(r.data));
  }

  // ── Turnos ──
  nuevoTurno(): void {
    this.turnoEdit.set({ id: 0, nombre: '', activo: true, rotacion_dias: 7,
      inicio_at: new Date().toISOString().slice(0, 10), participantes: [] });
  }
  editarTurno(t: TurnoOncall): void {
    this.turnoEdit.set({ ...t, inicio_at: (t.inicio_at || '').slice(0, 10),
      participantes: (t.participantes ?? []).map((p) => ({ perfil_id: p.perfil_id })) });
  }
  addParticipante(): void {
    const id = this.nuevoPerfil(); const t = this.turnoEdit();
    if (!id || !t) return;
    if ((t.participantes ?? []).some((p) => p.perfil_id === id)) return;
    t.participantes = [...(t.participantes ?? []), { perfil_id: id }];
    this.turnoEdit.set({ ...t }); this.nuevoPerfil.set('');
  }
  quitarParticipante(i: number): void {
    const t = this.turnoEdit(); if (!t) return;
    t.participantes!.splice(i, 1); this.turnoEdit.set({ ...t });
  }
  moverParticipante(i: number, d: number): void {
    const t = this.turnoEdit(); if (!t) return;
    const a = t.participantes!; const j = i + d;
    if (j < 0 || j >= a.length) return;
    [a[i], a[j]] = [a[j], a[i]]; this.turnoEdit.set({ ...t });
  }
  guardarTurno(): void {
    const t = this.turnoEdit(); if (!t) return;
    if (!t.nombre.trim()) { this.error.set('El turno necesita un nombre.'); return; }
    if ((t.participantes ?? []).length === 0) { this.error.set('Agrega al menos un participante.'); return; }
    this.error.set(null);
    const body = { nombre: t.nombre, activo: t.activo, rotacion_dias: t.rotacion_dias,
      inicio_at: t.inicio_at, participantes: t.participantes!.map((p) => p.perfil_id) };
    const obs = t.id ? this.svc.actualizarTurno(t.id, body) : this.svc.crearTurno(body);
    obs.subscribe({ next: () => { this.turnoEdit.set(null); this.cargar(); },
      error: (e) => this.error.set(this.msg(e)) });
  }
  eliminarTurno(t: TurnoOncall): void {
    if (!confirm(`¿Eliminar el turno "${t.nombre}"?`)) return;
    this.svc.eliminarTurno(t.id).subscribe({ next: () => this.cargar() });
  }

  // ── Políticas ──
  nuevaPolitica(): void {
    this.polEdit.set({ id: 0, nombre: '', activo: true, severidad_min: 'warning', descripcion: '',
      niveles: [{ espera_min: 10, destino_tipo: 'canal', canal_id: null }] });
  }
  editarPolitica(p: PoliticaEscalado): void {
    this.polEdit.set({ ...p, niveles: p.niveles.map((n) => ({ ...n })) });
  }
  addNivel(): void {
    const p = this.polEdit(); if (!p) return;
    const ultimo = p.niveles[p.niveles.length - 1];
    p.niveles = [...p.niveles, { espera_min: (ultimo?.espera_min ?? 0) + 10, destino_tipo: 'canal', canal_id: null }];
    this.polEdit.set({ ...p });
  }
  quitarNivel(i: number): void {
    const p = this.polEdit(); if (!p) return;
    p.niveles.splice(i, 1); this.polEdit.set({ ...p });
  }
  guardarPolitica(): void {
    const p = this.polEdit(); if (!p) return;
    if (!p.nombre.trim()) { this.error.set('La política necesita un nombre.'); return; }
    if (p.niveles.length === 0) { this.error.set('Agrega al menos un nivel.'); return; }
    this.error.set(null);
    const body = { nombre: p.nombre, activo: p.activo, severidad_min: p.severidad_min,
      descripcion: p.descripcion,
      niveles: p.niveles.map((n) => ({ espera_min: n.espera_min, destino_tipo: n.destino_tipo,
        canal_id: n.canal_id ?? null, turno_id: n.turno_id ?? null, perfil_id: n.perfil_id ?? null })) };
    const obs = p.id ? this.svc.actualizarPolitica(p.id, body) : this.svc.crearPolitica(body);
    obs.subscribe({ next: () => { this.polEdit.set(null); this.cargar(); },
      error: (e) => this.error.set(this.msg(e)) });
  }
  eliminarPolitica(p: PoliticaEscalado): void {
    if (!confirm(`¿Eliminar la política "${p.nombre}"?`)) return;
    this.svc.eliminarPolitica(p.id).subscribe({ next: () => this.cargar() });
  }

  // ── Helpers ──
  nombrePerfil(id?: string | null): string {
    const u = this.usuarios().find((x) => x.id === id);
    return u ? (u.nombre || u.email) : (id ?? '—');
  }
  destinoTexto(n: NivelEscalado): string {
    if (n.destino_tipo === 'canal') return 'Canal: ' + (n.canal_nombre ?? this.canales().find((c) => c.id === n.canal_id)?.nombre ?? '?');
    if (n.destino_tipo === 'turno') return 'Guardia: ' + (n.turno_nombre ?? this.turnos().find((t) => t.id === n.turno_id)?.nombre ?? '?');
    return 'Usuario: ' + (n.usuario_nombre ?? this.nombrePerfil(n.perfil_id));
  }
  sevLabel(s: Severidad): string {
    return { critical: 'Crítica', warning: 'Warning', info: 'Info' }[s];
  }
  private msg(e: unknown): string {
    return (e as { error?: { message?: string } })?.error?.message ?? 'Error al guardar.';
  }
}
