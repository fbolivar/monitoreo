<?php

namespace Tests\Feature;

use App\Models\Recurso;
use Illuminate\Foundation\Testing\DatabaseTransactions;
use Tests\Concerns\CreaUsuariosYTokens;
use Tests\TestCase;

class RecursoSecretosTest extends TestCase
{
    use DatabaseTransactions;
    use CreaUsuariosYTokens;

    public function test_los_secretos_nunca_se_devuelven_en_json(): void
    {
        $admin = $this->crearPerfil('admin');
        $tipo = $this->tipoRecurso();

        $resp = $this->postJson('/api/recursos', [
            'tipo_id'    => $tipo->id,
            'nombre'     => 'FW-con-secreto',
            'parametros' => ['port' => 161, 'snmp_version' => '2c'],
            'secretos'   => ['snmp_community' => 'super-secreto'],
        ], $this->authHeader($admin))->assertCreated();

        // La respuesta NO contiene la columna de secretos.
        $resp->assertJsonMissingPath('secretos');
        $resp->assertJsonPath('parametros.port', 161);

        $id = $resp->json('id');

        // El show tampoco expone secretos, pero informa que existen.
        $this->getJson("/api/recursos/{$id}", $this->authHeader($admin))
            ->assertOk()
            ->assertJsonMissingPath('secretos')
            ->assertJsonPath('tiene_secretos', true);

        // En BD el secreto está cifrado y se puede descifrar con la clave correcta.
        $recurso = Recurso::find($id);
        $this->assertSame(['snmp_community' => 'super-secreto'], $recurso->secretosDescifrados());

        // El valor crudo en columna NO es el texto plano.
        $crudo = \DB::table('recursos')->where('id', $id)->value('secretos');
        $this->assertNotNull($crudo);
        $this->assertStringNotContainsString('super-secreto', (string) $crudo);
    }

    public function test_actualizar_secreto_lo_reemplaza(): void
    {
        $admin = $this->crearPerfil('admin');
        $tipo = $this->tipoRecurso();

        $recurso = new Recurso(['tipo_id' => $tipo->id, 'nombre' => 'SW-1']);
        $recurso->setSecretosPlanos(['snmp_community' => 'v1']);
        $recurso->save();

        $this->patchJson("/api/recursos/{$recurso->id}", [
            'secretos' => ['snmp_community' => 'v2'],
        ], $this->authHeader($admin))->assertOk();

        $this->assertSame(['snmp_community' => 'v2'], $recurso->fresh()->secretosDescifrados());
    }
}
