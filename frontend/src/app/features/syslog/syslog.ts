import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { Severidad, SyslogEvento, SyslogRegla } from '../../core/models';
import { SyslogService } from '../../core/syslog.service';
import { AuthService } from '../../core/auth.service';
import { fecha } from '../../shared/tiempo';

/** Visor de eventos syslog (UDP/514). Filtros + autorrefresco. */
@Component({
  selector: 'app-syslog',
  standalone: true,
  imports: [FormsModule, RouterLink],
  templateUrl: './syslog.html',
  styleUrl: './syslog.scss',
})
export class Syslog implements OnInit, OnDestroy {
  private svc = inject(SyslogService);
  auth = inject(AuthService);
  fecha = fecha;

  eventos = signal<SyslogEvento[]>([]);
  total = signal(0);
  cargando = signal(true);
  fSeveridad = signal<'' | Severidad>('');
  fTexto = signal('');
  auto = signal(true);

  private timer: ReturnType<typeof setInterval> | null = null;

  ngOnInit(): void {
    this.cargar();
    this.timer = setInterval(() => { if (this.auto()) this.cargar(true); }, 15000);
  }
  ngOnDestroy(): void { if (this.timer) clearInterval(this.timer); }

  cargar(silencioso = false): void {
    if (!silencioso) this.cargando.set(true);
    this.svc.listar({
      severidad: this.fSeveridad() || undefined,
      texto: this.fTexto().trim() || undefined,
    }).subscribe({
      next: (p) => { this.eventos.set(p.data); this.total.set(p.total); this.cargando.set(false); },
      error: () => this.cargando.set(false),
    });
  }

  colorSev(s: Severidad): string {
    return { critical: '#d11d1d', warning: '#e0a400', info: '#9aa0a6' }[s];
  }

  // ── Reglas patrón→incidencia ──
  reglas = signal<SyslogRegla[]>([]);
  mostrarReglas = signal(false);
  reglaEdit = signal<SyslogRegla | null>(null);
  errorRegla = signal<string | null>(null);

  toggleReglas(): void {
    this.mostrarReglas.set(!this.mostrarReglas());
    if (this.mostrarReglas() && this.reglas().length === 0) this.cargarReglas();
  }
  cargarReglas(): void { this.svc.reglas().subscribe((r) => this.reglas.set(r.data)); }
  nuevaRegla(): void {
    this.errorRegla.set(null);
    this.reglaEdit.set({ nombre: '', activo: true, campo: 'mensaje', patron: '',
      accion: 'abrir', severidad: 'critical', clave: '', notificar: true });
  }
  editarRegla(r: SyslogRegla): void { this.errorRegla.set(null); this.reglaEdit.set({ ...r }); }
  guardarRegla(): void {
    const r = this.reglaEdit(); if (!r) return;
    if (!r.nombre.trim() || !r.patron.trim() || !r.clave.trim()) {
      this.errorRegla.set('Nombre, patrón y clave son obligatorios.'); return;
    }
    const obs = r.id ? this.svc.actualizarRegla(r.id, r) : this.svc.crearRegla(r);
    obs.subscribe({
      next: () => { this.reglaEdit.set(null); this.cargarReglas(); },
      error: (e) => this.errorRegla.set((e as { error?: { message?: string } })?.error?.message ?? 'Error al guardar.'),
    });
  }
  eliminarRegla(r: SyslogRegla): void {
    if (!r.id || !confirm(`¿Eliminar la regla "${r.nombre}"?`)) return;
    this.svc.eliminarRegla(r.id).subscribe(() => this.cargarReglas());
  }
}
