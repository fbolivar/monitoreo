<?php

namespace Tests\Feature;

use Illuminate\Foundation\Testing\DatabaseTransactions;
use Tests\Concerns\CreaUsuariosYTokens;
use Tests\TestCase;

class AutenticacionTest extends TestCase
{
    use DatabaseTransactions;
    use CreaUsuariosYTokens;

    public function test_rechaza_peticion_sin_token(): void
    {
        $this->getJson('/api/recursos')->assertStatus(401);
    }

    public function test_rechaza_token_con_firma_invalida(): void
    {
        $this->getJson('/api/recursos', $this->authHeaderInvalido())->assertStatus(401);
    }

    public function test_rechaza_usuario_sin_perfil(): void
    {
        // Token válido (firma correcta) pero el sub no tiene perfil.
        $this->getJson('/api/recursos', $this->authHeaderInvalido());
        // (cubierto arriba) — caso explícito de "sub sin perfil":
        $perfil = $this->crearPerfil('viewer');
        $header = $this->authHeader($perfil);
        $perfil->delete();

        $this->getJson('/api/me', $header)->assertStatus(403);
    }

    public function test_usuario_desactivado_no_accede(): void
    {
        $perfil = $this->crearPerfil('viewer', activo: false);

        $this->getJson('/api/me', $this->authHeader($perfil))->assertStatus(403);
    }

    public function test_token_valido_accede_a_me(): void
    {
        $perfil = $this->crearPerfil('viewer');

        $this->getJson('/api/me', $this->authHeader($perfil))
            ->assertOk()
            ->assertJsonPath('rol', 'viewer')
            ->assertJsonPath('id', $perfil->id);
    }
}
