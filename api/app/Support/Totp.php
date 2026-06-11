<?php

namespace App\Support;

/**
 * TOTP (RFC 6238) sin dependencias externas. Compatible con Google Authenticator,
 * Microsoft Authenticator, FreeOTP, etc. (HMAC-SHA1, 6 dígitos, periodo 30s).
 */
class Totp
{
    private const ALFABETO = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567'; // base32

    /** Genera un secreto base32 aleatorio. */
    public static function generarSecreto(int $longitud = 32): string
    {
        $bytes = random_bytes($longitud);
        $s = '';
        foreach (str_split($bytes) as $b) {
            $s .= self::ALFABETO[ord($b) % 32];
        }

        return $s;
    }

    /** URI otpauth:// para QR / alta manual en la app. */
    public static function uri(string $secreto, string $cuenta, string $emisor = 'SIMON'): string
    {
        return sprintf(
            'otpauth://totp/%s:%s?secret=%s&issuer=%s&algorithm=SHA1&digits=6&period=30',
            rawurlencode($emisor), rawurlencode($cuenta), $secreto, rawurlencode($emisor)
        );
    }

    /** Verifica un código de 6 dígitos con tolerancia de ±1 ventana (reloj desfasado). */
    public static function verificar(string $secreto, string $codigo, int $ventana = 1): bool
    {
        $codigo = preg_replace('/\D/', '', $codigo);
        if (strlen($codigo) !== 6) {
            return false;
        }
        $t = (int) floor(time() / 30);
        for ($i = -$ventana; $i <= $ventana; $i++) {
            if (hash_equals(self::codigoEn($secreto, $t + $i), $codigo)) {
                return true;
            }
        }

        return false;
    }

    private static function codigoEn(string $secreto, int $contador): string
    {
        $clave = self::base32Decode($secreto);
        $bin = pack('N*', 0).pack('N*', $contador);       // contador de 64 bits big-endian
        $hash = hash_hmac('sha1', $bin, $clave, true);
        $offset = ord($hash[strlen($hash) - 1]) & 0x0F;
        $parte = (
            ((ord($hash[$offset]) & 0x7F) << 24) |
            ((ord($hash[$offset + 1]) & 0xFF) << 16) |
            ((ord($hash[$offset + 2]) & 0xFF) << 8) |
            (ord($hash[$offset + 3]) & 0xFF)
        ) % 1000000;

        return str_pad((string) $parte, 6, '0', STR_PAD_LEFT);
    }

    private static function base32Decode(string $b32): string
    {
        $b32 = strtoupper(rtrim($b32, '='));
        $buffer = 0;
        $bits = 0;
        $salida = '';
        foreach (str_split($b32) as $c) {
            $v = strpos(self::ALFABETO, $c);
            if ($v === false) {
                continue;
            }
            $buffer = ($buffer << 5) | $v;
            $bits += 5;
            if ($bits >= 8) {
                $bits -= 8;
                $salida .= chr(($buffer >> $bits) & 0xFF);
            }
        }

        return $salida;
    }
}
