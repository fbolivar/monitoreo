import { DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FilaDisponibilidad, Pronostico, ReporteProgramado } from '../../core/models';
import { AuthService } from '../../core/auth.service';
import { ReportesService } from '../../core/reportes.service';
import { EstadoBadge } from '../../shared/estado-badge';
import { fecha } from '../../shared/tiempo';

type Rango = '24h' | '7d' | '30d';

@Component({
  selector: 'app-reportes',
  standalone: true,
  imports: [EstadoBadge, DecimalPipe, FormsModule],
  templateUrl: './reportes.html',
  styleUrl: './reportes.scss',
})
export class Reportes implements OnInit {
  private svc = inject(ReportesService);
  auth = inject(AuthService);
  fecha = fecha;

  rango = signal<Rango>('7d');
  filas = signal<FilaDisponibilidad[]>([]);
  desde = signal<string | null>(null);
  cargando = signal(true);

  // Pronósticos de capacidad (calculados por el worker). Urgentes primero.
  pronosticos = signal<Pronostico[]>([]);
  pronosticosAlerta = computed(() => this.pronosticos().filter((p) => p.dias_restantes != null));

  rangos: Rango[] = ['24h', '7d', '30d'];

  // Peor disponibilidad primero (los recursos con problemas arriba).
  ordenadas = computed(() =>
    [...this.filas()].sort((a, b) => (a.disponibilidad ?? 101) - (b.disponibilidad ?? 101)),
  );

  promedio = computed(() => {
    const v = this.filas().map((f) => f.disponibilidad).filter((x): x is number => x != null);
    return v.length ? v.reduce((s, x) => s + x, 0) / v.length : null;
  });

  totalIncidencias = computed(() => this.filas().reduce((s, f) => s + f.incidencias, 0));

  // Reportes programados (CRUD)
  programados = signal<ReporteProgramado[]>([]);
  editId = signal<number | null>(null);
  creando = signal(false);
  errorProg = signal<string | null>(null);
  fProg = this.progVacio();

  ngOnInit(): void {
    this.cargar();
    this.svc.pronosticos().subscribe((p) => this.pronosticos.set(p));
    this.cargarProgramados();
  }

  private progVacio() {
    return {
      nombre: '', periodo: 'mensual' as 'diario' | 'semanal' | 'mensual',
      rango: '30d' as '24h' | '7d' | '30d', destinatarios: '',
      formato: 'pdf' as 'pdf' | 'csv', activo: true,
    };
  }
  private cargarProgramados(): void {
    this.svc.programados().subscribe((p) => this.programados.set(p.data));
  }
  nuevoProg(): void { this.creando.set(true); this.editId.set(null); this.fProg = this.progVacio(); this.errorProg.set(null); }
  editarProg(r: ReporteProgramado): void {
    this.creando.set(false); this.editId.set(r.id); this.errorProg.set(null);
    this.fProg = {
      nombre: r.nombre, periodo: r.periodo, rango: r.rango,
      destinatarios: r.destinatarios, formato: r.formato, activo: r.activo,
    };
  }
  cancelarProg(): void { this.creando.set(false); this.editId.set(null); this.errorProg.set(null); }
  guardarProg(): void {
    const f = this.fProg;
    this.errorProg.set(null);
    if (!f.nombre.trim()) { this.errorProg.set('Indica un nombre.'); return; }
    if (!f.destinatarios.trim()) { this.errorProg.set('Indica al menos un correo.'); return; }
    const id = this.editId();
    const obs = id ? this.svc.actualizarProgramado(id, f) : this.svc.crearProgramado(f);
    obs.subscribe({
      next: () => { this.cancelarProg(); this.cargarProgramados(); },
      error: (e) => this.errorProg.set((e as { error?: { message?: string } })?.error?.message ?? 'Error al guardar.'),
    });
  }
  eliminarProg(r: ReporteProgramado): void {
    if (!confirm(`¿Eliminar el reporte programado "${r.nombre}"?`)) return;
    this.svc.eliminarProgramado(r.id).subscribe({ next: () => this.cargarProgramados() });
  }

  // Clase de urgencia según días restantes para llegar al techo.
  claseDias(d: number | null): string {
    if (d == null) return 'sd';
    if (d <= 7) return 'mal';
    if (d <= 30) return 'warn';
    return 'bien';
  }

  cambiarRango(r: Rango): void {
    this.rango.set(r);
    this.cargar();
  }

  private cargar(): void {
    this.cargando.set(true);
    this.svc.disponibilidad(this.rango()).subscribe({
      next: (r) => { this.filas.set(r.recursos); this.desde.set(r.desde); this.cargando.set(false); },
      error: () => this.cargando.set(false),
    });
  }

  clase(d: number | null): string {
    if (d == null) return 'sd';
    if (d >= 99.9) return 'ok';
    if (d >= 99) return 'bien';
    if (d >= 95) return 'warn';
    return 'mal';
  }

  exportarCsv(): void {
    const cab = ['Recurso', 'Tipo', 'Sitio', 'Estado', 'Disponibilidad %',
      'Up', 'Degradado', 'Caido', 'Desconocido', 'Mantenimiento', 'Incidencias'];
    const filas = this.ordenadas().map((f) => [
      f.nombre, f.tipo_nombre, f.sitio_nombre ?? '', f.estado_actual,
      f.disponibilidad ?? 'sin datos',
      f.up, f.degraded, f.down, f.unknown, f.mantenimiento, f.incidencias,
    ]);
    const csv = [cab, ...filas]
      .map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(','))
      .join('\r\n');

    const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `disponibilidad_${this.rango()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }
}
