<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<style>
    @page { margin: 120px 34px 70px 34px; }
    * { font-family: DejaVu Sans, sans-serif; }
    body { color: #1a2b21; font-size: 10px; }

    /* Encabezado corporativo (se repite en cada página) */
    .encabezado { position: fixed; top: -96px; left: 0; right: 0; height: 90px; }
    .encabezado table { width: 100%; border-bottom: 3px solid #2e7d3a; }
    .encabezado .logo { width: 150px; vertical-align: middle; }
    .encabezado .marca { text-align: right; vertical-align: middle; }
    .encabezado .marca .sim { font-size: 20px; font-weight: bold; color: #256a36; letter-spacing: .5px; }
    .encabezado .marca .ent { font-size: 9px; color: #5f6b62; }

    /* Pie de página */
    .pie { position: fixed; bottom: -50px; left: 0; right: 0; height: 36px;
           border-top: 1px solid #d7e0d9; color: #8a948c; font-size: 8px; padding-top: 5px; }
    .pie .izq { float: left; }
    .pie .der { float: right; }

    h1 { font-size: 17px; color: #256a36; margin: 0 0 2px; }
    .sub { color: #5f6b62; font-size: 10px; margin: 0 0 14px; }

    /* KPIs */
    .kpis { width: 100%; border-collapse: separate; border-spacing: 6px; margin-bottom: 14px; }
    .kpis td { width: 25%; background: #eaf3ec; border: 1px solid #cfe3d4; border-radius: 6px;
               padding: 8px 10px; vertical-align: top; }
    .kpis .v { font-size: 17px; font-weight: bold; color: #1a2b21; }
    .kpis .l { font-size: 8px; color: #5f6b62; text-transform: uppercase; }

    h2 { font-size: 12px; color: #256a36; margin: 16px 0 6px; padding-bottom: 3px;
         border-bottom: 1px solid #e0e8e2; }
    table.data { width: 100%; border-collapse: collapse; margin-bottom: 6px; }
    table.data th { background: #2e7d3a; color: #fff; text-align: left; padding: 5px 7px; font-size: 9px; }
    table.data td { padding: 4px 7px; border-bottom: 1px solid #e6ece8; font-size: 9px; }
    table.data tr:nth-child(even) td { background: #f5f9f6; }
    .vacia { color: #8a948c; font-style: italic; }
</style>
</head>
<body>
    <div class="encabezado">
        <table><tr>
            @if ($logo)<td><img src="{{ $logo }}" class="logo"></td>@endif
            <td class="marca">
                <div class="sim">SIMON</div>
                <div class="ent">Sistema Integral de Monitoreo · Parques Nacionales Naturales de Colombia</div>
            </td>
        </tr></table>
    </div>

    <div class="pie">
        <span class="izq">Parques Nacionales Naturales de Colombia — SIMON</span>
        <span class="der">Generado: {{ $generado }}</span>
    </div>

    <h1>{{ $data['titulo'] }}</h1>
    <div class="sub">{{ $data['subtitulo'] }}</div>

    @if (!empty($data['kpis']))
        <table class="kpis"><tr>
            @foreach ($data['kpis'] as $i => $k)
                <td>
                    <div class="v">{{ $k['valor'] }}</div>
                    <div class="l">{{ $k['label'] }}</div>
                </td>
                @if (($i + 1) % 4 == 0 && !$loop->last)</tr><tr>@endif
            @endforeach
        </tr></table>
    @endif

    @foreach ($data['tablas'] as $t)
        <h2>{{ $t['titulo'] }}</h2>
        <table class="data">
            <thead><tr>@foreach ($t['columnas'] as $c)<th>{{ $c }}</th>@endforeach</tr></thead>
            <tbody>
                @forelse ($t['filas'] as $f)
                    <tr>@foreach ($f as $c)<td>{{ $c }}</td>@endforeach</tr>
                @empty
                    <tr><td colspan="{{ count($t['columnas']) }}" class="vacia">Sin datos en el periodo.</td></tr>
                @endforelse
            </tbody>
        </table>
    @endforeach
</body>
</html>
