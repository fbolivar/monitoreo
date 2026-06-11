<?php

use App\Http\Middleware\EnsureRole;
use App\Http\Middleware\VerifyJwt;
use Illuminate\Foundation\Application;
use Illuminate\Database\QueryException;
use Illuminate\Foundation\Configuration\Exceptions;
use Illuminate\Foundation\Configuration\Middleware;
use Illuminate\Http\Request;
use Illuminate\Validation\ValidationException;
use Symfony\Component\HttpKernel\Exception\HttpExceptionInterface;

return Application::configure(basePath: dirname(__DIR__))
    ->withRouting(
        web: __DIR__.'/../routes/web.php',
        api: __DIR__.'/../routes/api.php',
        commands: __DIR__.'/../routes/console.php',
        health: '/up',
    )
    ->withMiddleware(function (Middleware $middleware) {
        // Alias de middleware usados en routes/api.php
        $middleware->alias([
            'auth.jwt' => VerifyJwt::class,
            'role'     => EnsureRole::class,
        ]);
    })
    ->withExceptions(function (Exceptions $exceptions) {
        // Respuestas JSON consistentes para toda la API.
        $exceptions->render(function (\Throwable $e, Request $request) {
            if (! $request->is('api/*') && ! $request->expectsJson()) {
                return null;
            }

            if ($e instanceof ValidationException) {
                return response()->json([
                    'message' => 'Datos inválidos.',
                    'errors'  => $e->errors(),
                ], 422);
            }

            // Violaciones de integridad de Postgres (FK/único/check) -> 409 claro
            // en vez de un 500 genérico (p.ej. borrar un tipo con recursos en uso).
            if ($e instanceof QueryException) {
                $sqlState = $e->errorInfo[0] ?? null;
                if (in_array($sqlState, ['23503', '23505', '23514'], true)) {
                    return response()->json([
                        'message' => 'No se puede completar la operación: el registro está en uso o viola una restricción de integridad.',
                    ], 409);
                }
            }

            $status = $e instanceof HttpExceptionInterface ? $e->getStatusCode() : 500;

            return response()->json([
                'message' => $status === 500 ? 'Error interno del servidor.' : $e->getMessage(),
            ], $status);
        });
    })->create();
