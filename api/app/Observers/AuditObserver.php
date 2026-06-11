<?php

namespace App\Observers;

use App\Support\Auditoria;
use Illuminate\Database\Eloquent\Model;

/**
 * Observa el CRUD de las entidades de configuración y lo vuelca en la bitácora.
 * Solo registra cuando hay un usuario autenticado en el request (acciones de
 * gestión vía API); las escrituras del worker (Python) no pasan por aquí.
 */
class AuditObserver
{
    /** Campos que nunca se vuelcan en el diff (ruido o sensibles). */
    private const DENY = ['updated_at', 'created_at', 'secretos', 'password_hash', 'totp_secret'];

    public function created(Model $m): void
    {
        if (! $this->actorPresente()) {
            return;
        }
        Auditoria::registrar('crear', $m->getTable(), $m->getKey(), $this->etiqueta($m));
    }

    public function updated(Model $m): void
    {
        if (! $this->actorPresente()) {
            return;
        }
        $cambios = [];
        foreach ($m->getChanges() as $campo => $nuevo) {
            if (in_array($campo, self::DENY, true)) {
                continue;
            }
            $cambios[$campo] = [$m->getOriginal($campo), $nuevo];
        }
        if (! $cambios) {
            return; // nada relevante cambió
        }
        Auditoria::registrar('actualizar', $m->getTable(), $m->getKey(), $this->etiqueta($m), $cambios);
    }

    public function deleted(Model $m): void
    {
        if (! $this->actorPresente()) {
            return;
        }
        Auditoria::registrar('eliminar', $m->getTable(), $m->getKey(), $this->etiqueta($m));
    }

    private function actorPresente(): bool
    {
        return request()->user() !== null;
    }

    /** Etiqueta legible del objeto, según el atributo disponible. */
    private function etiqueta(Model $m): ?string
    {
        return $m->nombre ?? $m->email ?? $m->metrica ?? $m->titulo ?? (string) $m->getKey();
    }
}
