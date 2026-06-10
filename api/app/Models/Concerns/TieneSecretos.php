<?php

namespace App\Models\Concerns;

use Illuminate\Support\Facades\DB;

/**
 * Cifrado transparente de SECRETOS para el resto de la app.
 *
 * Mecanismo (FASE 1): la columna `secretos` (bytea) guarda el resultado de
 * pgcrypto `pgp_sym_encrypt` (AES-256). La clave maestra (APP_CRYPTO_KEY) vive
 * solo en la API y se pasa como parámetro vinculado; NUNCA se almacena en BD.
 *
 * Uso desde controladores:
 *   $modelo->setSecretosPlanos(['snmp_community' => '...']);  // o null para borrar
 *   $modelo->save();                                          // cifra al persistir
 *   $modelo->secretosDescifrados();                           // lee descifrado (bajo demanda)
 *
 * La columna `secretos` se oculta de toda serialización JSON (ver $hidden del
 * modelo + initialize()), de modo que jamás se devuelve en las respuestas.
 */
trait TieneSecretos
{
    /** Valor en claro pendiente de cifrar (set por la app). */
    protected ?array $secretosPendientes = null;

    /** Indica si setSecretosPlanos() fue invocado en esta instancia. */
    protected bool $secretosTocados = false;

    public static function bootTieneSecretos(): void
    {
        // Tras insertar/actualizar (ya hay PK), persistimos el secreto cifrado.
        static::saved(function ($model) {
            $model->persistirSecretos();
        });
    }

    public function initializeTieneSecretos(): void
    {
        // Garantiza que la columna binaria nunca se serialice.
        if (! in_array('secretos', $this->hidden, true)) {
            $this->hidden[] = 'secretos';
        }
    }

    /**
     * Define los secretos en claro a guardar. Pasar null o [] borra el secreto.
     */
    public function setSecretosPlanos(?array $data): void
    {
        $this->secretosPendientes = $data;
        $this->secretosTocados = true;
    }

    /**
     * Persiste el secreto cifrado vía pgcrypto. Llamado automáticamente en saved().
     */
    protected function persistirSecretos(): void
    {
        if (! $this->secretosTocados) {
            return;
        }
        $this->secretosTocados = false;

        $tabla = $this->getTable();
        $pk    = $this->getKeyName();
        $id    = $this->getKey();

        if (empty($this->secretosPendientes)) {
            DB::table($tabla)->where($pk, $id)->update(['secretos' => null]);
            return;
        }

        $clave = $this->claveCifrado();
        DB::statement(
            "UPDATE {$tabla} SET secretos = cifrar_secreto(?::jsonb, ?) WHERE {$pk} = ?",
            [json_encode($this->secretosPendientes), $clave, $id]
        );
    }

    /**
     * Devuelve los secretos descifrados (array) o null si no hay. Bajo demanda;
     * jamás se incluye en la serialización del modelo.
     */
    public function secretosDescifrados(): ?array
    {
        $tabla = $this->getTable();
        $pk    = $this->getKeyName();

        $row = DB::selectOne(
            "SELECT descifrar_secreto(secretos, ?) AS s FROM {$tabla} WHERE {$pk} = ?",
            [$this->claveCifrado(), $this->getKey()]
        );

        if (! $row || $row->s === null) {
            return null;
        }

        return json_decode($row->s, true);
    }

    /** Indica si el registro tiene secretos almacenados (sin descifrarlos). */
    public function tieneSecretos(): bool
    {
        $row = DB::selectOne(
            "SELECT (secretos IS NOT NULL) AS tiene FROM {$this->getTable()} WHERE {$this->getKeyName()} = ?",
            [$this->getKey()]
        );

        return (bool) ($row->tiene ?? false);
    }

    protected function claveCifrado(): string
    {
        $clave = config('app.crypto_key');
        if (! $clave) {
            throw new \RuntimeException('APP_CRYPTO_KEY no configurada: no se pueden cifrar/descifrar secretos.');
        }

        return $clave;
    }
}
