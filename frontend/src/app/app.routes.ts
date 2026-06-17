import { Routes } from '@angular/router';
import { adminGuard, authGuard } from './core/guards';
import { Shell } from './layout/shell';

export const routes: Routes = [
  {
    path: 'login',
    loadComponent: () => import('./features/auth/login').then((m) => m.Login),
  },
  {
    // Tablero NOC a pantalla completa (fuera del Shell).
    path: 'wallboard',
    canActivate: [authGuard],
    loadComponent: () => import('./features/wallboard/wallboard').then((m) => m.Wallboard),
  },
  {
    path: '',
    component: Shell,
    canActivate: [authGuard],
    children: [
      {
        path: '',
        loadComponent: () => import('./features/dashboard/dashboard').then((m) => m.Dashboard),
      },
      {
        path: 'recursos',
        loadComponent: () => import('./features/recursos/recursos').then((m) => m.Recursos),
      },
      {
        path: 'sitios',
        loadComponent: () => import('./features/sitios/sitios').then((m) => m.Sitios),
      },
      {
        path: 'recursos/:id',
        loadComponent: () =>
          import('./features/recurso-detalle/recurso-detalle').then((m) => m.RecursoDetalle),
      },
      {
        path: 'incidencias',
        loadComponent: () => import('./features/incidencias/incidencias').then((m) => m.Incidencias),
      },
      {
        path: 'traps',
        loadComponent: () => import('./features/traps/traps').then((m) => m.Traps),
      },
      {
        path: 'descubrimiento',
        loadComponent: () =>
          import('./features/descubrimiento/descubrimiento').then((m) => m.Descubrimiento),
      },
      {
        path: 'reportes',
        loadComponent: () => import('./features/reportes/reportes').then((m) => m.Reportes),
      },
      {
        path: 'topologia',
        loadComponent: () => import('./features/topologia/topologia').then((m) => m.Topologia),
      },
      {
        path: 'mapa',
        loadComponent: () => import('./features/mapa/mapa').then((m) => m.Mapa),
      },
      {
        path: 'servicios',
        loadComponent: () => import('./features/servicios/servicios').then((m) => m.Servicios),
      },
      {
        path: 'configuracion',
        loadComponent: () =>
          import('./features/configuracion/configuracion').then((m) => m.Configuracion),
      },
      {
        path: 'seguridad',
        loadComponent: () => import('./features/seguridad/seguridad').then((m) => m.Seguridad),
      },
      {
        path: 'usuarios',
        canActivate: [adminGuard],
        loadComponent: () => import('./features/usuarios/usuarios').then((m) => m.Usuarios),
      },
      {
        path: 'auditoria',
        canActivate: [adminGuard],
        loadComponent: () => import('./features/auditoria/auditoria').then((m) => m.Auditoria),
      },
    ],
  },
  { path: '**', redirectTo: '' },
];
