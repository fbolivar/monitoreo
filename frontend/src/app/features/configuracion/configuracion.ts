import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../../core/auth.service';
import { ConfigService } from '../../core/config.service';
import {
  Canal, LdapConfig, Mantenimiento, OPERADORES, Recurso, Sitio, TIPOS_CANAL, TipoRecurso, Umbral,
} from '../../core/models';
import { RecursosService } from '../../core/recursos.service';
import { fecha } from '../../shared/tiempo';

type Tab = 'umbrales' | 'mantenimientos' | 'canales' | 'autenticacion';

@Component({
  selector: 'app-configuracion',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './configuracion.html',
  styleUrl: './configuracion.scss',
})
export class Configuracion implements OnInit {
  private cfg = inject(ConfigService);
  private recSvc = inject(RecursosService);
  auth = inject(AuthService);

  readonly operadores = OPERADORES;
  readonly tiposCanal = TIPOS_CANAL;
  fecha = fecha;

  tab = signal<Tab>('umbrales');
  error = signal<string | null>(null);

  // Catálogos para selects
  recursos = signal<Recurso[]>([]);
  tipos = signal<TipoRecurso[]>([]);
  sitios = signal<Sitio[]>([]);

  // Datos
  umbrales = signal<Umbral[]>([]);
  mantenimientos = signal<Mantenimiento[]>([]);
  canales = signal<Canal[]>([]);

  // Formularios (objetos mutables para ngModel)
  editId = signal<number | null>(null);
  creando = signal(false);

  fUmbral = this.umbralVacio();
  fMant = this.mantVacio();
  fCanal = this.canalVacio();

  // LDAP / SSO
  fLdap: LdapConfig = { enabled: false, host: '', port: 389, use_tls: false, bind_pattern: '{user}', rol_default: 'viewer', group_dn: '', auto_create: true, usuarios_permitidos: '' };
  ldapDisponible = signal(true);
  ldapGuardado = signal(false);
  ldapTest = { test_usuario: '', test_password: '' };
  ldapResultado = signal<{ ok: boolean; mensaje: string } | null>(null);
  ldapProbando = signal(false);

  ngOnInit(): void {
    this.recSvc.listar({ per_page: 200 }).subscribe((p) => this.recursos.set(p.data));
    this.recSvc.tipos().subscribe((p) => this.tipos.set(p.data));
    this.recSvc.sitios().subscribe((p) => this.sitios.set(p.data));
    this.recargar();
  }

  cambiarTab(t: Tab): void {
    this.tab.set(t);
    this.cancelar();
    this.recargar();
  }

  recargar(): void {
    this.error.set(null);
    if (this.tab() === 'umbrales') this.cfg.umbrales().subscribe((p) => this.umbrales.set(p.data));
    if (this.tab() === 'mantenimientos') this.cfg.mantenimientos().subscribe((p) => this.mantenimientos.set(p.data));
    if (this.tab() === 'canales') this.cfg.canales().subscribe((p) => this.canales.set(p.data));
    if (this.tab() === 'autenticacion') {
      this.ldapResultado.set(null); this.ldapGuardado.set(false);
      this.cfg.ldapObtener().subscribe((r) => { this.fLdap = r.config; this.ldapDisponible.set(r.disponible); });
    }
  }

  guardarLdap(): void {
    this.error.set(null); this.ldapGuardado.set(false);
    this.cfg.ldapGuardar(this.fLdap).subscribe({
      next: () => this.ldapGuardado.set(true),
      error: (e) => this.error.set(this.msg(e)),
    });
  }

  probarLdap(): void {
    this.ldapResultado.set(null); this.ldapProbando.set(true);
    this.cfg.ldapProbar({
      host: this.fLdap.host, port: this.fLdap.port, use_tls: this.fLdap.use_tls,
      bind_pattern: this.fLdap.bind_pattern,
      test_usuario: this.ldapTest.test_usuario, test_password: this.ldapTest.test_password,
    }).subscribe({
      next: (r) => { this.ldapResultado.set(r); this.ldapProbando.set(false); },
      error: (e) => { this.ldapResultado.set({ ok: false, mensaje: this.msg(e) }); this.ldapProbando.set(false); },
    });
  }

  cancelar(): void {
    this.creando.set(false);
    this.editId.set(null);
    this.error.set(null);
  }

  nombreRecurso(id?: number | null): string {
    return this.recursos().find((r) => r.id === id)?.nombre ?? (id ? `#${id}` : '—');
  }
  nombreTipo(id?: number | null): string {
    return this.tipos().find((t) => t.id === id)?.nombre ?? (id ? `#${id}` : '—');
  }
  nombreSitio(id?: number | null): string {
    return this.sitios().find((s) => s.id === id)?.nombre ?? (id ? `#${id}` : '—');
  }
  private msg(e: unknown): string {
    return (e as { error?: { message?: string } })?.error?.message ?? 'Error al guardar.';
  }

  // ── UMBRALES ──────────────────────────────────────────────────────
  private umbralVacio() {
    return {
      ambito: 'tipo' as 'tipo' | 'recurso',
      recurso_id: null as number | null,
      tipo_id: null as number | null,
      metrica: '', operador: '>', valor_warning: null as number | null,
      valor_critical: null as number | null, duracion_segundos: 0, activo: true,
    };
  }
  nuevoUmbral(): void { this.creando.set(true); this.editId.set(null); this.fUmbral = this.umbralVacio(); }
  editarUmbral(u: Umbral): void {
    this.creando.set(false); this.editId.set(u.id);
    this.fUmbral = {
      ambito: u.recurso_id ? 'recurso' : 'tipo',
      recurso_id: u.recurso_id ?? null, tipo_id: u.tipo_id ?? null,
      metrica: u.metrica, operador: u.operador,
      valor_warning: u.valor_warning ?? null, valor_critical: u.valor_critical ?? null,
      duracion_segundos: u.duracion_segundos, activo: u.activo,
    };
  }
  guardarUmbral(): void {
    const f = this.fUmbral;
    this.error.set(null);
    if (f.ambito === 'recurso' && !f.recurso_id) { this.error.set('Selecciona un recurso.'); return; }
    if (f.ambito === 'tipo' && !f.tipo_id) { this.error.set('Selecciona un tipo.'); return; }
    if (!f.metrica.trim()) { this.error.set('Indica la métrica.'); return; }
    const body: Record<string, unknown> = {
      recurso_id: f.ambito === 'recurso' ? f.recurso_id : null,
      tipo_id: f.ambito === 'tipo' ? f.tipo_id : null,
      metrica: f.metrica, operador: f.operador,
      valor_warning: f.valor_warning, valor_critical: f.valor_critical,
      duracion_segundos: f.duracion_segundos, activo: f.activo,
    };
    const id = this.editId();
    const obs = id ? this.cfg.actualizarUmbral(id, body) : this.cfg.crearUmbral(body);
    obs.subscribe({ next: () => { this.cancelar(); this.recargar(); }, error: (e) => this.error.set(this.msg(e)) });
  }
  eliminarUmbral(u: Umbral): void {
    if (!confirm('¿Eliminar umbral?')) return;
    this.cfg.eliminarUmbral(u.id).subscribe({ next: () => this.recargar(), error: (e) => this.error.set(this.msg(e)) });
  }

  // ── MANTENIMIENTOS ────────────────────────────────────────────────
  private mantVacio() {
    return {
      ambito: 'recurso' as 'recurso' | 'sitio' | 'global',
      recurso_id: null as number | null, sitio_id: null as number | null,
      inicio: '', fin: '', motivo: '',
    };
  }
  nuevoMant(): void { this.creando.set(true); this.editId.set(null); this.fMant = this.mantVacio(); }
  editarMant(m: Mantenimiento): void {
    this.creando.set(false); this.editId.set(m.id);
    this.fMant = {
      ambito: m.recurso_id ? 'recurso' : m.sitio_id ? 'sitio' : 'global',
      recurso_id: m.recurso_id ?? null, sitio_id: m.sitio_id ?? null,
      inicio: m.inicio?.slice(0, 16) ?? '', fin: m.fin?.slice(0, 16) ?? '', motivo: m.motivo,
    };
  }
  guardarMant(): void {
    const f = this.fMant;
    this.error.set(null);
    if (f.ambito === 'recurso' && !f.recurso_id) { this.error.set('Selecciona un recurso.'); return; }
    if (f.ambito === 'sitio' && !f.sitio_id) { this.error.set('Selecciona un sitio.'); return; }
    if (!f.inicio || !f.fin || !f.motivo.trim()) { this.error.set('Completa inicio, fin y motivo.'); return; }
    const body: Record<string, unknown> = {
      recurso_id: f.ambito === 'recurso' ? f.recurso_id : null,
      sitio_id: f.ambito === 'sitio' ? f.sitio_id : null,
      inicio: f.inicio, fin: f.fin, motivo: f.motivo,
    };
    const id = this.editId();
    const obs = id ? this.cfg.actualizarMantenimiento(id, body) : this.cfg.crearMantenimiento(body);
    obs.subscribe({ next: () => { this.cancelar(); this.recargar(); }, error: (e) => this.error.set(this.msg(e)) });
  }
  eliminarMant(m: Mantenimiento): void {
    if (!confirm('¿Eliminar mantenimiento?')) return;
    this.cfg.eliminarMantenimiento(m.id).subscribe({ next: () => this.recargar(), error: (e) => this.error.set(this.msg(e)) });
  }

  // ── CANALES ───────────────────────────────────────────────────────
  private canalVacio() {
    return { tipo: 'email', nombre: '', configTexto: '{}', secretosTexto: '', activo: true };
  }
  nuevoCanal(): void { this.creando.set(true); this.editId.set(null); this.fCanal = this.canalVacio(); }
  editarCanal(c: Canal): void {
    this.creando.set(false); this.editId.set(c.id);
    this.fCanal = {
      tipo: c.tipo, nombre: c.nombre,
      configTexto: JSON.stringify(c.config ?? {}, null, 2), secretosTexto: '', activo: c.activo,
    };
  }
  guardarCanal(): void {
    const f = this.fCanal;
    let config: unknown = {};
    try { config = f.configTexto.trim() ? JSON.parse(f.configTexto) : {}; }
    catch { this.error.set('Config: JSON inválido.'); return; }
    const body: Record<string, unknown> = { tipo: f.tipo, nombre: f.nombre, config, activo: f.activo };
    if (f.secretosTexto.trim()) {
      try { body['secretos'] = JSON.parse(f.secretosTexto); }
      catch { this.error.set('Secretos: JSON inválido.'); return; }
    }
    const id = this.editId();
    const obs = id ? this.cfg.actualizarCanal(id, body) : this.cfg.crearCanal(body);
    obs.subscribe({ next: () => { this.cancelar(); this.recargar(); }, error: (e) => this.error.set(this.msg(e)) });
  }
  eliminarCanal(c: Canal): void {
    if (!confirm('¿Eliminar canal?')) return;
    this.cfg.eliminarCanal(c.id).subscribe({ next: () => this.recargar(), error: (e) => this.error.set(this.msg(e)) });
  }
}
