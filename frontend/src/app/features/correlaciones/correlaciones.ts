import { Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Correlacion } from '../../core/models';
import { OperacionService } from '../../core/operacion.service';
import { fecha } from '../../shared/tiempo';

/** AIOps (#14): incidencias correlacionadas (reducción de ruido). */
@Component({
  selector: 'app-correlaciones',
  standalone: true,
  imports: [RouterLink],
  template: `
    <div class="head"><h1>Correlación de alertas <span class="text-dim">· AIOps</span></h1></div>
    <p class="intro text-dim">El worker agrupa incidencias relacionadas (misma sede + ventana de tiempo)
      en un solo evento y marca la causa raíz probable, para que 10 alertas de un parque sean «1 evento».</p>

    @if (cargando()) { <p class="text-dim">Cargando…</p> }
    @else if (lista().length === 0) { <p class="text-dim">Aún no hay correlaciones.</p> }
    @else {
      @for (c of lista(); track c.id) {
        <section class="card">
          <div class="ch">
            <b>{{ c.sitio_nombre || 'Sin sede' }}</b>
            <span class="badge">{{ c.n_incidencias }} incidencias</span>
            <span class="text-dim">{{ fecha(c.creada_at) }}</span>
          </div>
          <p class="res text-dim">{{ c.resumen }}</p>
          <ul>
            @for (i of c.incidencias; track i.id) {
              <li [class.causa]="i.id === c.causa_incidencia_id">
                <span class="sev" [attr.data-s]="i.severidad"></span>
                <a [routerLink]="['/incidencias']">{{ i.recurso_nombre }}: {{ i.titulo }}</a>
                @if (i.id === c.causa_incidencia_id) { <span class="tag">causa raíz</span> }
              </li>
            }
          </ul>
        </section>
      }
    }
  `,
  styles: [`
    .head h1 { font-size: 18px; margin: 8px 0; }
    .intro { font-size: 12.5px; margin: 0 0 14px; max-width: 800px; }
    .card { background: #fff; border: 1px solid var(--border); border-radius: var(--radius); padding: 12px 14px; margin-bottom: 12px; }
    .ch { display: flex; align-items: center; gap: 12px; }
    .badge { font-size: 11px; padding: 2px 9px; border-radius: 10px; background: #fdecec; color: #c0392b; font-weight: 700; }
    .res { font-size: 12.5px; margin: 6px 0 8px; }
    ul { list-style: none; margin: 0; padding: 0; }
    li { display: flex; align-items: center; gap: 8px; padding: 4px 0; font-size: 13px; }
    li.causa { font-weight: 700; }
    .sev { width: 9px; height: 9px; border-radius: 50%; background: #9ca3af; }
    .sev[data-s=critical] { background: #d11d1d; } .sev[data-s=warning] { background: #e0a400; }
    .tag { font-size: 10px; background: #14532d; color: #fff; padding: 1px 7px; border-radius: 8px; }
  `],
})
export class Correlaciones implements OnInit {
  private svc = inject(OperacionService);
  lista = signal<Correlacion[]>([]);
  cargando = signal(true);
  fecha = fecha;

  ngOnInit(): void {
    this.svc.correlaciones().subscribe({
      next: (p) => { this.lista.set(p.data); this.cargando.set(false); },
      error: () => this.cargando.set(false),
    });
  }
}
