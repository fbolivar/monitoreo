<?php

namespace App\Support;

/**
 * Formato de respaldo propio .pnnc (Parques Nacionales Naturales de Colombia).
 *
 * Contenedor portable y autodescrito para un respaldo de la BD de SIMON.
 * Estructura binaria (big-endian) — espejo EXACTO de monitor/respaldo_pnnc.py:
 *
 *   [0:8]      magia  = "PNNCBK" + version_mayor(1B) + version_menor(1B)
 *   [8:12]     uint32 = longitud M de la metadata JSON
 *   [12:12+M]  metadata JSON (UTF-8)
 *   [12+M:]    payload (bytes del pg_dump -Fc, opcionalmente cifrado openssl)
 *
 * El sha256 de la metadata es del payload tal cual queda en el archivo (ya
 * cifrado si aplica), para verificar integridad antes de descifrar/restaurar.
 */
class RespaldoPnnc
{
    public const MAGIA = 'PNNCBK';
    public const VERSION = [1, 0];
    private const CABECERA_FIJA = 6 + 2 + 4; // magia + version(2) + uint32

    /**
     * Arma el contenedor .pnnc. Sella sha256/tam_payload en la metadata.
     */
    public static function empacar(string $payload, array $meta): string
    {
        $meta['sha256'] = hash('sha256', $payload);
        $meta['tam_payload'] = strlen($payload);
        $metaBytes = json_encode($meta, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
        $cabecera = self::MAGIA . chr(self::VERSION[0]) . chr(self::VERSION[1])
            . pack('N', strlen($metaBytes));
        return $cabecera . $metaBytes . $payload;
    }

    /**
     * Construye SOLO la cabecera (magia + version + metadata) a partir de una
     * metadata que YA trae sha256/tam_payload. Para escribir el .pnnc por
     * streaming sin cargar el payload (varios MB) en memoria:
     *   fwrite($f, RespaldoPnnc::cabecera($meta)); stream_copy_to_stream($dump, $f);
     */
    public static function cabecera(array $meta): string
    {
        $metaBytes = json_encode($meta, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
        return self::MAGIA . chr(self::VERSION[0]) . chr(self::VERSION[1])
            . pack('N', strlen($metaBytes)) . $metaBytes;
    }

    /**
     * Lee SOLO la metadata (sin cargar el payload). Lanza si la magia es inválida.
     * Útil para listar: leer los primeros ~8 KB del archivo basta.
     */
    public static function leerMetadata(string $blob): array
    {
        if (strlen($blob) < self::CABECERA_FIJA || substr($blob, 0, 6) !== self::MAGIA) {
            throw new \RuntimeException('no es un archivo .pnnc (magia inválida)');
        }
        if (ord($blob[6]) !== self::VERSION[0]) {
            throw new \RuntimeException('versión .pnnc no soportada: ' . ord($blob[6]));
        }
        $m = unpack('N', substr($blob, 8, 4))[1];
        $fin = self::CABECERA_FIJA + $m;
        if (strlen($blob) < $fin) {
            throw new \RuntimeException('cabecera truncada');
        }
        $meta = json_decode(substr($blob, self::CABECERA_FIJA, $m), true);
        if (! is_array($meta)) {
            throw new \RuntimeException('metadata ilegible');
        }
        return $meta;
    }

    /**
     * Devuelve ['meta' => array, 'payload' => string]. Si $verificar, valida el sha256.
     */
    public static function desempacar(string $blob, bool $verificar = true): array
    {
        $meta = self::leerMetadata($blob);
        $m = unpack('N', substr($blob, 8, 4))[1];
        $payload = substr($blob, self::CABECERA_FIJA + $m);
        if ($verificar && ! empty($meta['sha256']) && $meta['sha256'] !== hash('sha256', $payload)) {
            throw new \RuntimeException('integridad: sha256 no coincide');
        }
        return ['meta' => $meta, 'payload' => $payload];
    }
}
