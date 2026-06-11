import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';
import { AuthService } from './auth.service';

/** Ante un 401 con sesión activa (token caducado/invalidado), cierra sesión y
 *  redirige a /login para que la app no quede en un estado inconsistente. */
export const errorInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  const router = inject(Router);
  return next(req).pipe(
    catchError((err: HttpErrorResponse) => {
      if (err.status === 401 && auth.autenticado()) {
        void auth.cerrarSesion();
        void router.navigate(['/login']);
      }
      return throwError(() => err);
    }),
  );
};
