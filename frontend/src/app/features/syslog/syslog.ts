import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { Severidad, SyslogEvento } from '../../core/models';
import { SyslogService } from '../../core/syslog.service';
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
}
