import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FlujoAgregado, FlujosResp } from '../../core/models';
import { RecursosService } from '../../core/recursos.service';

type Rango = '1h' | '6h' | '24h' | '7d';

@Component({
  selector: 'app-flujos',
  standalone: true,
  imports: [],
  templateUrl: './flujos.html',
  styleUrl: './flujos.scss',
})
export class Flujos implements OnInit {
  private svc = inject(RecursosService);

  data = signal<FlujosResp | null>(null);
  cargando = signal(true);
  rango = signal<Rango>('1h');

  rangos: Rango[] = ['1h', '6h', '24h', '7d'];

  ngOnInit(): void { this.cargar(); }

  cambiar(r: Rango): void { this.rango.set(r); this.cargar(); }

  cargar(): void {
    this.cargando.set(true);
    this.svc.flujos({ rango: this.rango() }).subscribe({
      next: (d) => { this.data.set(d); this.cargando.set(false); },
      error: () => this.cargando.set(false),
    });
  }

  totalBytes = computed(() => this.data()?.total_bytes ?? 0);

  // % relativo respecto al mayor de la lista (para la barra).
  pct(fila: FlujoAgregado, lista: FlujoAgregado[]): number {
    const max = lista.length ? Math.max(...lista.map((f) => f.bytes)) : 0;
    return max > 0 ? Math.round((fila.bytes / max) * 100) : 0;
  }

  fmtBytes(b: number): string {
    if (b < 1024) return `${b} B`;
    const u = ['KB', 'MB', 'GB', 'TB'];
    let v = b / 1024, i = 0;
    while (v >= 1024 && i < u.length - 1) { v /= 1024; i++; }
    return `${v.toFixed(v >= 100 ? 0 : 1)} ${u[i]}`;
  }

  proto(n: number | null | undefined): string {
    return ({ 1: 'ICMP', 6: 'TCP', 17: 'UDP', 47: 'GRE', 50: 'ESP' } as Record<number, string>)[n ?? -1]
      || (n != null ? String(n) : '—');
  }
}
