<?php

namespace Tests\Feature;

use App\Models\Recurso;
use Illuminate\Foundation\Testing\DatabaseTransactions;
use Illuminate\Support\Facades\DB;
use Tests\Concerns\CreaUsuariosYTokens;
use Tests\TestCase;

class LecturaFiltrosTest extends TestCase
{
    use DatabaseTransactions;
    use CreaUsuariosYTokens;

    public function test_metricas_filtra_por_recurso_y_rango_de_fechas(): void
    {
        $viewer = $this->crearPerfil('viewer');
        $tipo = $this->tipoRecurso();
        $recurso = Recurso::create(['tipo_id' => $tipo->id, 'nombre' => 'SRV-metricas']);

        // 3 métricas: dos dentro del rango, una fuera.
        DB::table('metricas')->insert([
            ['recurso_id' => $recurso->id, 'metrica' => 'cpu', 'valor' => 10, 'unidad' => '%', 'ts' => now()->subMinutes(10)],
            ['recurso_id' => $recurso->id, 'metrica' => 'cpu', 'valor' => 20, 'unidad' => '%', 'ts' => now()->subMinutes(5)],
            ['recurso_id' => $recurso->id, 'metrica' => 'cpu', 'valor' => 99, 'unidad' => '%', 'ts' => now()->subDays(3)],
        ]);

        $resp = $this->getJson(
            '/api/metricas?recurso_id='.$recurso->id.'&metrica=cpu&desde='.now()->subHour()->toIso8601String(),
            $this->authHeader($viewer)
        )->assertOk();

        // Solo las dos dentro de la última hora.
        $this->assertCount(2, $resp->json('data'));
    }

    public function test_chequeos_filtra_por_estado(): void
    {
        $viewer = $this->crearPerfil('viewer');
        $tipo = $this->tipoRecurso();
        $recurso = Recurso::create(['tipo_id' => $tipo->id, 'nombre' => 'SRV-chequeos']);

        DB::table('chequeos')->insert([
            ['recurso_id' => $recurso->id, 'ts' => now(), 'estado' => 'up', 'latencia_ms' => 5, 'detalle' => '{}'],
            ['recurso_id' => $recurso->id, 'ts' => now(), 'estado' => 'down', 'latencia_ms' => null, 'detalle' => '{}'],
        ]);

        $resp = $this->getJson(
            '/api/chequeos?recurso_id='.$recurso->id.'&estado=down',
            $this->authHeader($viewer)
        )->assertOk();

        $this->assertCount(1, $resp->json('data'));
        $this->assertSame('down', $resp->json('data.0.estado'));
    }
}
