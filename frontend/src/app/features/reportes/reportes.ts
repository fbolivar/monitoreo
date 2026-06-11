import { DecimalPipe } from '@angular/common';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FilaDisponibilidad } from '../../core/models';
import { ReportesService } from '../../core/reportes.service';
import { EstadoBadge } from '../../shared/estado-badge';

type Rango = '24h' | '7d' | '30d';

@Component({
  selector: 'app-reportes',
  standalone: true,
  imports: [EstadoBadge, DecimalPipe],
  templateUrl: './reportes.html',
  styleUrl: './reportes.scss',
})
export class Reportes implements OnInit {
  private svc = inject(ReportesService);

  rango = signal<Rango>('7d');
  filas = signal<FilaDisponibilidad[]>([]);
  desde = signal<string | null>(null);
  cargando = signal(true);

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

  ngOnInit(): void {
    this.cargar();
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
