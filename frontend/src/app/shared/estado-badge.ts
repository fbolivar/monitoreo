import { Component, input } from '@angular/core';
import { Estado, ESTADO_LABEL } from '../core/models';

/** Semáforo de estado: punto de color + etiqueta. */
@Component({
  selector: 'app-estado-badge',
  standalone: true,
  template: `
    <span class="badge" [title]="label()">
      <span class="dot" [class]="'bg-' + estado()"></span>
      @if (texto()) {
        <span>{{ label() }}</span>
      }
    </span>
  `,
  styles: [
    `
      .badge { display: inline-flex; align-items: center; gap: 6px; white-space: nowrap; }
    `,
  ],
})
export class EstadoBadge {
  estado = input.required<Estado>();
  texto = input(true);
  label = () => ESTADO_LABEL[this.estado()] ?? this.estado();
}
