import { Routes } from '@angular/router';
import { adminGuard, authGuard } from './core/guards';
import { Shell } from './layout/shell';

export const routes: Routes = [
  {
    path: 'login',
    loadComponent: () => import('./features/auth/login').then((m) => m.Login),
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
        path: 'reportes',
        loadComponent: () => import('./features/reportes/reportes').then((m) => m.Reportes),
      },
      {
        path: 'mapa',
        loadComponent: () => import('./features/mapa/mapa').then((m) => m.Mapa),
      },
      {
        path: 'configuracion',
        loadComponent: () =>
          import('./features/configuracion/configuracion').then((m) => m.Configuracion),
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
