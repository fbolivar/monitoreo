<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;

class Sitio extends Model
{
    protected $table = 'sitios';

    protected $fillable = [
        'codigo', 'nombre', 'direccion', 'ciudad',
        'latitud', 'longitud', 'descripcion', 'activo',
    ];

    protected $casts = [
        'latitud'  => 'float',
        'longitud' => 'float',
        'activo'   => 'boolean',
    ];

    public function recursos(): HasMany
    {
        return $this->hasMany(Recurso::class, 'sitio_id');
    }
}
