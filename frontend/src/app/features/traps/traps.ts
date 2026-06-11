import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Trap } from '../../core/models';
import { TrapsService } from '../../core/traps.service';
import { fecha } from '../../shared/tiempo';

@Component({
  selector: 'app-traps',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './traps.html',
  styleUrl: './traps.scss',
})
export class Traps implements OnInit {
  private svc = inject(TrapsService);

  traps = signal<Trap[]>([]);
  total = signal(0);
  cargando = signal(true);
  fSeveridad = signal('');
  expandida = signal<number | null>(null);

  fecha = fecha;

  ngOnInit(): void { this.cargar(); }

  cargar(): void {
    this.cargando.set(true);
    this.svc.listar({ severidad: this.fSeveridad() || undefined }).subscribe({
      next: (p) => { this.traps.set(p.data); this.total.set(p.total); this.cargando.set(false); },
      error: () => this.cargando.set(false),
    });
  }

  toggle(id: number): void { this.expandida.set(this.expandida() === id ? null : id); }

  claves(v: Record<string, string> | null): string[] { return v ? Object.keys(v) : []; }
}
