<?php

namespace Tests\Feature;

use Illuminate\Foundation\Testing\DatabaseTransactions;
use Tests\Concerns\CreaUsuariosYTokens;
use Tests\TestCase;

class AutorizacionRolTest extends TestCase
{
    use DatabaseTransactions;
    use CreaUsuariosYTokens;

    public function test_viewer_puede_leer_pero_no_escribir(): void
    {
        $viewer = $this->crearPerfil('viewer');
        $header = $this->authHeader($viewer);
        $tipo = $this->tipoRecurso();

        // Lectura permitida
        $this->getJson('/api/recursos', $header)->assertOk();

        // Escritura prohibida (403)
        $this->postJson('/api/recursos', [
            'tipo_id' => $tipo->id,
            'nombre'  => 'No debería crearse',
        ], $header)->assertStatus(403);
    }

    public function test_operador_puede_crear_configuracion(): void
    {
        $operador = $this->crearPerfil('operador');
        $tipo = $this->tipoRecurso();

        $this->postJson('/api/recursos', [
            'tipo_id'  => $tipo->id,
            'nombre'   => 'SRV-operador',
            'hostname' => '10.9.9.9',
        ], $this->authHeader($operador))
            ->assertCreated()
            ->assertJsonPath('nombre', 'SRV-operador');
    }

    public function test_operador_no_accede_a_usuarios(): void
    {
        $operador = $this->crearPerfil('operador');

        $this->getJson('/api/usuarios', $this->authHeader($operador))->assertStatus(403);
    }

    public function test_admin_accede_a_usuarios(): void
    {
        $admin = $this->crearPerfil('admin');

        $this->getJson('/api/usuarios', $this->authHeader($admin))->assertOk();
    }
}
