<?php

namespace App\Http\Controllers;

use Illuminate\Http\JsonResponse;
use Illuminate\Support\Facades\DB;

/** Virtualización (#9): inventario de VMs de un host (lectura). */
class VmController extends Controller
{
    public function index(int $id): JsonResponse
    {
        $vms = DB::table('vm_inventario')
            ->where('host_recurso_id', $id)
            ->orderBy('nombre')
            ->get();

        return response()->json([
            'total'      => $vms->count(),
            'encendidas' => $vms->where('power_state', 'POWERED_ON')->count(),
            'vms'        => $vms->values(),
        ]);
    }
}
