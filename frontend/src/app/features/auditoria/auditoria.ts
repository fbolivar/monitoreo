import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AuditoriaEntrada } from '../../core/models';
import { AuditoriaService } from '../../core/auditoria.service';
import { fecha } from '../../shared/tiempo';

@Component({
  selector: 'app-auditoria',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './auditoria.html',
  styleUrl: './auditoria.scss',
})
export class Auditoria implements OnInit {
  private svc = inject(AuditoriaService);

  entradas = signal<AuditoriaEntrada[]>([]);
  cargando = signal(true);
  total = signal(0);

  fAccion = signal('');
  fEntidad = signal('');
  buscar = signal('');
  expandida = signal<number | null>(null);

  acciones = ['crear', 'actualizar', 'eliminar', 'login', 'login_fallido'];
  entidades = ['recursos', 'sitios', 'umbrales', 'mantenimientos', 'canales_notificacion',
    'tipos_recurso', 'perfiles', 'incidencias', 'auth'];

  fecha = fecha;

  ngOnInit(): void {
    this.cargar();
  }

  cargar(): void {
    this.cargando.set(true);
    this.svc.listar({
      accion: this.fAccion() || undefined,
      entidad: this.fEntidad() || undefined,
      buscar: this.buscar().trim() || undefined,
    }).subscribe({
      next: (p) => { this.entradas.set(p.data); this.total.set(p.total); this.cargando.set(false); },
      error: () => this.cargando.set(false),
    });
  }

  toggle(id: number): void {
    this.expandida.set(this.expandida() === id ? null : id);
  }

  campos(c: Record<string, [unknown, unknown]> | null): string[] {
    return c ? Object.keys(c) : [];
  }

  fmt(v: unknown): string {
    if (v === null || v === undefined) return '∅';
    if (typeof v === 'object') return JSON.stringify(v);
    return String(v);
  }
}
