<?php

namespace App\Support;

use Illuminate\Support\Facades\DB;

/**
 * Alcance por usuario: a qué sitios (territoriales) puede acceder el perfil autenticado.
 *
 * Es una barrera REAL, no cosmética: se aplica en la API. Un usuario acotado no
 * obtiene datos ajenos ni llamando al endpoint directamente ni manipulando la
 * petición — ocultarlo solo en la UI sería seguridad de mentira.
 *
 * Reglas (deliberadas):
 *   - SIN filas en `perfil_sitios` = SIN restricción (retrocompatible: hoy nadie
 *     está acotado, todo sigue igual). Acotar es opt-in explícito.
 *   - Los ADMIN nunca se acotan (administran el sistema y asignan los alcances).
 *   - Un recurso sin sitio (NULL) NO es visible para un perfil acotado: no
 *     pertenece a ninguna territorial. Por eso se usa whereIn, que ya excluye NULL.
 *
 * Se resuelve una vez por petición (cache estática).
 */
class Alcance
{
    private static bool $resueltoSitios = false;
    private static ?array $sitios = null;
    private static bool $resueltoRecursos = false;
    private static ?array $recursos = null;

    /** Sitios permitidos, o null si el usuario NO está acotado. */
    public static function sitios(): ?array
    {
        if (self::$resueltoSitios) {
            return self::$sitios;
        }
        self::$resueltoSitios = true;
        self::$sitios = null;

        $perfil = request()?->attributes->get('perfil');
        if (! $perfil || ($perfil->rol ?? null) === 'admin') {
            return null;   // sin perfil resuelto (o admin) -> sin restricción
        }

        $ids = DB::table('perfil_sitios')->where('perfil_id', $perfil->id)->pluck('sitio_id')->all();
        self::$sitios = empty($ids) ? null : array_map('intval', $ids);

        return self::$sitios;
    }

    public static function restringido(): bool
    {
        return self::sitios() !== null;
    }

    /**
     * IDs de recurso permitidos, o null si no está acotado. Para las tablas de
     * telemetría (chequeos, métricas, traps…), que se filtran por recurso_id.
     */
    public static function recursos(): ?array
    {
        if (self::$resueltoRecursos) {
            return self::$recursos;
        }
        self::$resueltoRecursos = true;
        $sitios = self::sitios();
        self::$recursos = $sitios === null
            ? null
            : array_map('intval', DB::table('recursos')->whereIn('sitio_id', $sitios)->pluck('id')->all());

        return self::$recursos;
    }

    /** ¿Puede ver este recurso? (para los endpoints /recursos/{id}/...) */
    public static function permiteRecurso(?int $recursoId): bool
    {
        $permitidos = self::recursos();

        return $permitidos === null || ($recursoId !== null && in_array($recursoId, $permitidos, true));
    }

    /** ¿Puede ver este sitio? */
    public static function permiteSitio(?int $sitioId): bool
    {
        $sitios = self::sitios();

        return $sitios === null || ($sitioId !== null && in_array($sitioId, $sitios, true));
    }

    /** Filtra un query por la columna de sitio (tabla recursos/sitios). */
    public static function filtrarPorSitio($q, string $col = 'sitio_id')
    {
        $sitios = self::sitios();
        if ($sitios !== null) {
            $q->whereIn($col, $sitios);   // excluye tambien los sitio_id NULL: correcto
        }

        return $q;
    }

    /** Filtra un query por recurso_id (telemetría e incidencias). */
    public static function filtrarPorRecurso($q, string $col = 'recurso_id')
    {
        $rec = self::recursos();
        if ($rec !== null) {
            $q->whereIn($col, $rec ?: [-1]);   // sin recursos permitidos -> no devuelve nada
        }

        return $q;
    }

    /**
     * Lista de IDs de recurso para SQL crudo, o null si no aplica. Se devuelve
     * como array para pasarlo con bindings (nunca interpolar en el SQL).
     */
    public static function idsParaSql(): ?array
    {
        $rec = self::recursos();

        return $rec === null ? null : ($rec ?: [-1]);
    }
}
