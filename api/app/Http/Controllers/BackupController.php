<?php

namespace App\Http\Controllers;

use App\Support\Auditoria;
use App\Support\RespaldoPnnc;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\BinaryFileResponse;
use Symfony\Component\Process\Process;

/**
 * Módulo de respaldo .pnnc (formato propio PNNC). Genera respaldos de la BD de
 * SIMON en un contenedor portable y autodescrito (.pnnc) y permite EXPORTARLOS
 * (descargarlos) para llevarlos fuera del servidor. Solo admin.
 *
 * - generar:  pg_dump -Fc -> (cifrado openssl opcional) -> envoltorio .pnnc.
 * - descargar: exporta el .pnnc tal cual (para guardarlo off-site).
 * - La RESTAURACIÓN no se expone por web (es destructiva): va por shell con
 *   infra/deploy/restaurar_pnnc.sh.
 */
class BackupController extends Controller
{
    /** Nombre válido de un .pnnc generado por SIMON (evita path traversal). */
    private const NOMBRE_RE = '/^simon_\d{8}_\d{6}\.pnnc$/';

    /** Lista los respaldos .pnnc disponibles (lee solo la cabecera de cada uno). */
    public function index(): JsonResponse
    {
        $dir = config('respaldo.dir');
        $items = [];
        foreach (glob($dir.'/simon_*.pnnc') ?: [] as $ruta) {
            $items[] = $this->describir($ruta);
        }
        // Más recientes primero.
        usort($items, fn ($a, $b) => strcmp($b['id'], $a['id']));

        return response()->json([
            'data' => $items,
            'dir'  => $dir,
            'formato' => 'pnnc',
        ]);
    }

    /** Genera un respaldo nuevo. Acepta `passphrase` opcional para cifrarlo. */
    public function generar(Request $request): JsonResponse
    {
        $data = $request->validate([
            'passphrase' => ['nullable', 'string', 'min:8', 'max:128'],
            'nota'       => ['nullable', 'string', 'max:200'],
        ]);

        $dir = config('respaldo.dir');
        if (! is_dir($dir) || ! is_writable($dir)) {
            return response()->json([
                'message' => "La carpeta de respaldos no existe o no es escribible: $dir",
            ], 500);
        }

        $db = config('database.connections.'.config('database.default'));
        $ts = now()->format('Ymd_His');
        $tmpDump = tempnam(sys_get_temp_dir(), 'simon_dump_');
        $tmpPay = $tmpDump; // payload = dump, salvo que se cifre
        $cifrado = 'none';

        try {
            // 1) pg_dump en formato custom (-Fc), comprimido internamente.
            $this->correr(
                [config('respaldo.pg_dump'), '-h', $db['host'], '-p', (string) $db['port'],
                 '-U', $db['username'], '-d', $db['database'], '-Fc', '-f', $tmpDump],
                ['PGPASSWORD' => $db['password']],
            );

            // 2) Cifrado opcional (openssl, compatible con la CLI para restaurar).
            if (! empty($data['passphrase'])) {
                $tmpPay = tempnam(sys_get_temp_dir(), 'simon_enc_');
                $this->correr(
                    [config('respaldo.openssl'), 'enc', '-aes-256-cbc', '-pbkdf2', '-salt',
                     '-in', $tmpDump, '-out', $tmpPay, '-pass', 'env:PNNC_PASS'],
                    ['PNNC_PASS' => $data['passphrase']],
                );
                $cifrado = 'aes-256-cbc-pbkdf2';
            }

            // 3) Envoltorio .pnnc por streaming (sin cargar el payload en memoria).
            $meta = [
                'producto'        => 'SIMON',
                'entidad'         => 'Parques Nacionales Naturales de Colombia',
                'creado_en'       => now()->utc()->toIso8601ZuluString(),
                'servidor'        => gethostname() ?: null,
                'base_datos'      => $db['database'],
                'formato_payload' => 'pgdump-custom',
                'cifrado'         => $cifrado,
                'sha256'          => hash_file('sha256', $tmpPay),
                'tam_payload'     => filesize($tmpPay),
                'app_version'     => trim(@file_get_contents(base_path('VERSION')) ?: '') ?: null,
                'nota'            => $data['nota'] ?? null,
            ];
            $destino = $dir.'/simon_'.$ts.'.pnnc';
            $this->escribirContenedor($destino, $meta, $tmpPay);
        } catch (\Throwable $e) {
            return response()->json(['message' => 'Falló la generación del respaldo: '.$e->getMessage()], 500);
        } finally {
            @unlink($tmpDump);
            if ($tmpPay !== $tmpDump) {
                @unlink($tmpPay);
            }
        }

        $this->rotar($dir, (int) config('respaldo.retener'));

        $info = $this->describir($destino);
        Auditoria::registrar('generar', 'respaldo', $info['id'],
            'Respaldo .pnnc generado'.($cifrado !== 'none' ? ' (cifrado)' : ''));

        return response()->json(['data' => $info, 'message' => 'Respaldo generado'], 201);
    }

    /** Exporta (descarga) un .pnnc. */
    public function descargar(string $id): BinaryFileResponse|JsonResponse
    {
        $ruta = $this->rutaSegura($id);
        if (! $ruta) {
            return response()->json(['message' => 'Respaldo no encontrado'], 404);
        }
        Auditoria::registrar('descargar', 'respaldo', $id, 'Exportó el respaldo .pnnc');

        return response()->download($ruta, $id, [
            'Content-Type' => 'application/octet-stream',
        ]);
    }

    /** Elimina un .pnnc. */
    public function eliminar(string $id): JsonResponse
    {
        $ruta = $this->rutaSegura($id);
        if (! $ruta) {
            return response()->json(['message' => 'Respaldo no encontrado'], 404);
        }
        @unlink($ruta);
        Auditoria::registrar('eliminar', 'respaldo', $id, 'Eliminó el respaldo .pnnc');

        return response()->json(['message' => 'Respaldo eliminado']);
    }

    // ── helpers ──────────────────────────────────────────────────────────────

    /** Valida el id contra path traversal y devuelve la ruta si existe. */
    private function rutaSegura(string $id): ?string
    {
        if (! preg_match(self::NOMBRE_RE, $id)) {
            return null;
        }
        $ruta = config('respaldo.dir').'/'.$id;

        return is_file($ruta) ? $ruta : null;
    }

    /** Metadata + tamaño de un .pnnc, leyendo solo su cabecera. */
    private function describir(string $ruta): array
    {
        $id = basename($ruta);
        $meta = [];
        try {
            $fh = fopen($ruta, 'rb');
            $cab = $fh ? fread($fh, 8192) : '';
            if ($fh) {
                fclose($fh);
            }
            $meta = RespaldoPnnc::leerMetadata($cab);
        } catch (\Throwable) {
            $meta = ['error' => 'cabecera ilegible'];
        }

        return [
            'id'          => $id,
            'tam'         => is_file($ruta) ? filesize($ruta) : 0,
            'creado_en'   => $meta['creado_en'] ?? null,
            'cifrado'     => $meta['cifrado'] ?? null,
            'sha256'      => $meta['sha256'] ?? null,
            'base_datos'  => $meta['base_datos'] ?? null,
            'servidor'    => $meta['servidor'] ?? null,
            'nota'        => $meta['nota'] ?? null,
            'app_version' => $meta['app_version'] ?? null,
        ];
    }

    /** Escribe el contenedor .pnnc: cabecera + copia del payload por streaming. */
    private function escribirContenedor(string $destino, array $meta, string $payloadPath): void
    {
        $tmp = $destino.'.tmp';
        $out = fopen($tmp, 'wb');
        $in = fopen($payloadPath, 'rb');
        if (! $out || ! $in) {
            throw new \RuntimeException('no se pudo abrir el destino del respaldo');
        }
        try {
            fwrite($out, RespaldoPnnc::cabecera($meta));
            if (stream_copy_to_stream($in, $out) === false) {
                throw new \RuntimeException('fallo copiando el payload');
            }
        } finally {
            fclose($in);
            fclose($out);
        }
        if (! rename($tmp, $destino)) {
            @unlink($tmp);
            throw new \RuntimeException('no se pudo finalizar el respaldo');
        }
    }

    /** Ejecuta un proceso con timeout y env extra; lanza con stderr si falla. */
    private function correr(array $cmd, array $env = []): void
    {
        $p = new Process($cmd, null, $env + ['PATH' => getenv('PATH') ?: '/usr/bin:/bin']);
        $p->setTimeout((float) config('respaldo.timeout'));
        $p->run();
        if (! $p->isSuccessful()) {
            // No filtrar la passphrase: el stderr de openssl/pg_dump no la incluye.
            throw new \RuntimeException(trim($p->getErrorOutput()) ?: 'proceso con código '.$p->getExitCode());
        }
    }

    /** Conserva los N .pnnc más recientes; borra el resto. */
    private function rotar(string $dir, int $retener): void
    {
        if ($retener <= 0) {
            return;
        }
        $files = glob($dir.'/simon_*.pnnc') ?: [];
        rsort($files); // por nombre (timestamp) desc
        foreach (array_slice($files, $retener) as $viejo) {
            @unlink($viejo);
        }
    }
}
