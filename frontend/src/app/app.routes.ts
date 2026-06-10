import { Routes } from '@angular/router';
import { authGuard } from './core/guards';
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
        path: 'recursos/:id',
        loadComponent: () =>
          import('./features/recurso-detalle/recurso-detalle').then((m) => m.RecursoDetalle),
      },
      {
        path: 'incidencias',
        loadComponent: () => import('./features/incidencias/incidencias').then((m) => m.Incidencias),
      },
      {
        path: 'configuracion',
        loadComponent: () =>
          import('./features/configuracion/configuracion').then((m) => m.Configuracion),
      },
    ],
  },
  { path: '**', redirectTo: '' },
];
