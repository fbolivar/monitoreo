<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<style>
    @page { margin: 38px 36px 58px 36px; }
    * { font-family: DejaVu Sans, sans-serif; }
    body { color: #1a2b21; font-size: 10px; }

    /* Encabezado institucional (página 1) */
    .hdr { width: 100%; border-collapse: collapse; border-bottom: 3px solid #2e7d3a; margin-bottom: 14px; }
    .hdr td { vertical-align: middle; padding-bottom: 8px; }
    .hdr .marca { text-align: right; }
    .hdr .marca .sim { font-size: 20px; font-weight: bold; color: #256a36; letter-spacing: .5px; }
    .hdr .marca .ent { font-size: 9px; color: #5f6b62; }

    h1 { font-size: 16px; color: #256a36; margin: 0 0 2px; }
    .sub { color: #5f6b62; font-size: 10px; margin: 0 0 14px; }

    /* KPIs */
    .kpis { width: 100%; border-collapse: separate; border-spacing: 6px; margin-bottom: 12px; }
    .kpis td { width: 25%; background: #eaf3ec; border: 1px solid #cfe3d4; padding: 7px 9px; vertical-align: top; }
    .kpis .v { font-size: 16px; font-weight: bold; color: #1a2b21; }
    .kpis .l { font-size: 8px; color: #5f6b62; text-transform: uppercase; }

    h2 { font-size: 12px; color: #256a36; margin: 14px 0 5px; padding-bottom: 3px; border-bottom: 1px solid #e0e8e2; }
    table.data { width: 100%; border-collapse: collapse; margin-bottom: 6px; }
    table.data th { background: #2e7d3a; color: #fff; text-align: left; padding: 5px 7px; font-size: 9px; }
    table.data td { padding: 4px 7px; border-bottom: 1px solid #e6ece8; font-size: 9px; }
    table.data tr:nth-child(even) td { background: #f5f9f6; }
    .vacia { color: #8a948c; font-style: italic; }
</style>
</head>
<body>
    <table class="hdr"><tr>
        @if ($logo)<td><img src="{{ $logo }}" width="150" alt=""></td>@endif
        <td class="marca">
            <div class="sim">SIMON</div>
            <div class="ent">Sistema Integral de Monitoreo · Parques Nacionales Naturales de Colombia</div>
        </td>
    </tr></table>

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
