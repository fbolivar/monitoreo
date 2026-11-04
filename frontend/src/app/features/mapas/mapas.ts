import { Component, OnDestroy, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { EnlaceMapa, Estado, MapaPersonalizado, MapaResumen, NodoMapa } from '../../core/models';
import { MapasService } from '../../core/mapas.service';
import { RecursosService } from '../../core/recursos.service';
import { AuthService } from '../../core/auth.service';

@Component({
  selector: 'app-mapas',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './mapas.html',
  styleUrl: './mapas.scss',
})
export class Mapas implements OnInit, OnDestroy {
  private svc = inject(MapasService);
  private recursosSvc = inject(RecursosService);
  private router = inject(Router);
  auth = inject(AuthService);

  lista = signal<MapaResumen[]>([]);
  mapa = signal<MapaPersonalizado | null>(null);
  editando = signal(false);
  estados = signal<Map<number, Estado>>(new Map());
  recursos = signal<EnlaceMapa[]>([]);     // del endpoint /mapa: id, nombre, estado
  seleccion = signal<string | null>(null); // nodo seleccionado
  modo = signal<'mover' | 'conectar'>('mover');
  conectarDesde = signal<string | null>(null);
  nuevoRecurso = signal<number | ''>('');

  private timer: ReturnType<typeof setInterval> | null = null;
  private drag: { id: string; movido: boolean } | null = null;

  ngOnInit(): void {
    this.svc.listar().subscribe((r) => { this.lista.set(r.data); if (r.data[0]) this.abrir(r.data[0].id); });
    this.cargarEstados();
    this.timer = setInterval(() => this.cargarEstados(), 15000);
  }
  ngOnDestroy(): void { if (this.timer) clearInterval(this.timer); }

  private cargarEstados(): void {
    this.recursosSvc.mapa().subscribe((r) => {
      this.recursos.set(r.enlaces);
      const m = new Map<number, Estado>();
      for (const e of r.enlaces) m.set(e.id, e.estado_actual);
      this.estados.set(m);
    });
  }

  abrir(id: number): void {
    this.editando.set(false); this.seleccion.set(null);
    this.svc.obtener(id).subscribe((m) => {
      m.layout = m.layout ?? { nodos: [], enlaces: [] };
      m.layout.nodos = m.layout.nodos ?? []; m.layout.enlaces = m.layout.enlaces ?? [];
      this.mapa.set(m);
    });
  }

  estadoNodo(n: NodoMapa): Estado {
    if (n.tipo !== 'recurso' || n.recurso_id == null) return 'unknown';
    return this.estados().get(n.recurso_id) ?? 'unknown';
  }
  color(e: Estado): string {
    return { up: '#1b8a3a', degraded: '#e0a400', down: '#d11d1d', unknown: '#9aa0a6', maintenance: '#3b82f6' }[e];
  }
  etiquetaNodo(n: NodoMapa): string {
    if (n.etiqueta) return n.etiqueta;
    if (n.tipo === 'recurso') return this.recursos().find((r) => r.id === n.recurso_id)?.nombre ?? ('#' + n.recurso_id);
    return 'texto';
  }
  nodo(id: string): NodoMapa | undefined { return this.mapa()?.layout.nodos.find((n) => n.id === id); }

  // ── CRUD de mapas ──
  nuevoMapa(): void {
    const nombre = prompt('Nombre del mapa:')?.trim(); if (!nombre) return;
    this.svc.crear({ nombre, ancho: 1200, alto: 700, layout: { nodos: [], enlaces: [] } })
      .subscribe((r) => { this.svc.listar().subscribe((l) => this.lista.set(l.data)); this.abrir(r.id); this.editando.set(true); });
  }
  eliminarMapa(): void {
    const m = this.mapa(); if (!m || !confirm(`¿Eliminar el mapa "${m.nombre}"?`)) return;
    this.svc.eliminar(m.id).subscribe(() => { this.mapa.set(null); this.svc.listar().subscribe((l) => this.lista.set(l.data)); });
  }
  guardar(): void {
    const m = this.mapa(); if (!m) return;
    this.svc.actualizar(m.id, { nombre: m.nombre, fondo_url: m.fondo_url, ancho: m.ancho, alto: m.alto, layout: m.layout })
      .subscribe(() => { this.editando.set(false); this.svc.listar().subscribe((l) => this.lista.set(l.data)); });
  }

  // ── Edición de nodos ──
  private nid(): string { return 'n' + Date.now().toString(36) + Math.floor(Math.random() * 1e4).toString(36); }
  addRecurso(): void {
    const m = this.mapa(); const rid = this.nuevoRecurso(); if (!m || rid === '') return;
    m.layout.nodos.push({ id: this.nid(), tipo: 'recurso', recurso_id: +rid, x: m.ancho / 2, y: m.alto / 2 });
    this.mapa.set({ ...m }); this.nuevoRecurso.set('');
  }
  addTexto(): void {
    const m = this.mapa(); if (!m) return;
    const t = prompt('Texto:')?.trim(); if (!t) return;
    m.layout.nodos.push({ id: this.nid(), tipo: 'texto', etiqueta: t, x: m.ancho / 2, y: m.alto / 2 });
    this.mapa.set({ ...m });
  }
  eliminarNodo(): void {
    const m = this.mapa(); const id = this.seleccion(); if (!m || !id) return;
    m.layout.nodos = m.layout.nodos.filter((n) => n.id !== id);
    m.layout.enlaces = m.layout.enlaces.filter((e) => e.a !== id && e.b !== id);
    this.seleccion.set(null); this.mapa.set({ ...m });
  }

  private conectar(n: NodoMapa): void {
    const desde = this.conectarDesde();
    if (!desde) { this.conectarDesde.set(n.id); return; }
    if (desde !== n.id) {
      const m = this.mapa()!;
      if (!m.layout.enlaces.some((e) => (e.a === desde && e.b === n.id) || (e.a === n.id && e.b === desde))) {
        m.layout.enlaces.push({ a: desde, b: n.id }); this.mapa.set({ ...m });
      }
    }
    this.conectarDesde.set(null);
  }

  // ── Arrastre / clic de nodos (pointer) ──
  pDown(ev: PointerEvent, n: NodoMapa): void {
    if (this.editando() && this.modo() === 'mover') {
      this.drag = { id: n.id, movido: false };
      (ev.target as Element).setPointerCapture?.(ev.pointerId);
    }
    ev.stopPropagation();
  }
  pMove(ev: PointerEvent): void {
    if (!this.drag) return;
    const m = this.mapa(); if (!m) return;
    const svg = (ev.currentTarget as SVGSVGElement).getBoundingClientRect();
    const x = Math.round((ev.clientX - svg.left) / svg.width * m.ancho);
    const y = Math.round((ev.clientY - svg.top) / svg.height * m.alto);
    const nodo = m.layout.nodos.find((z) => z.id === this.drag!.id);
    if (nodo) { nodo.x = Math.max(0, Math.min(x, m.ancho)); nodo.y = Math.max(0, Math.min(y, m.alto)); this.drag.movido = true; this.mapa.set({ ...m }); }
  }
  pUp(_ev: PointerEvent, n?: NodoMapa): void {
    const movido = this.drag?.movido;
    this.drag = null;
    if (!n) return;
    if (this.editando() && this.modo() === 'conectar') { this.conectar(n); return; }
    if (this.editando()) { if (!movido) this.seleccion.set(this.seleccion() === n.id ? null : n.id); return; }
    this.verRecurso(n);
  }

  verRecurso(n: NodoMapa): void {
    if (!this.editando() && n.tipo === 'recurso' && n.recurso_id) this.router.navigate(['/recursos', n.recurso_id]);
  }

  recursosOrdenados = computed(() => [...this.recursos()].sort((a, b) => a.nombre.localeCompare(b.nombre)));
}
