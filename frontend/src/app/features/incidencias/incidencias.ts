import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { EstadoIncidencia, Incidencia, Severidad } from '../../core/models';
import { TelemetriaService } from '../../core/telemetria.service';
import { duracion, fecha } from '../../shared/tiempo';

@Component({
  selector: 'app-incidencias',
  standalone: true,
  imports: [FormsModule, RouterLink],
  templateUrl: './incidencias.html',
  styleUrl: './incidencias.scss',
})
export class Incidencias implements OnInit {
  private tele = inject(TelemetriaService);

  incidencias = signal<Incidencia[]>([]);
  cargando = signal(true);

  vista = signal<'activas' | 'historico'>('activas');
  fSeveridad = signal<Severidad | ''>('');

  fecha = fecha;
  duracion = duracion;

  filtradas = computed(() => {
    const activas = this.vista() === 'activas';
    const sev = this.fSeveridad();
    return this.incidencias().filter((i) => {
      const esActiva = i.estado !== 'resuelta';
      if (activas && !esActiva) return false;
      if (sev && i.severidad !== sev) return false;
      return true;
    });
  });

  ngOnInit(): void {
    this.cargar();
  }

  cargar(): void {
    this.cargando.set(true);
    this.tele.incidencias({ per_page: 200 }).subscribe({
      next: (p) => { this.incidencias.set(p.data); this.cargando.set(false); },
      error: () => this.cargando.set(false),
    });
  }

  estadoLabel(e: EstadoIncidencia): string {
    return { abierta: 'Abierta', reconocida: 'Reconocida', resuelta: 'Resuelta' }[e];
  }
}
