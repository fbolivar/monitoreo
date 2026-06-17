<?php

namespace App\Http\Controllers;

use App\Support\ReporteData;
use App\Support\ReporteExport;
use Dompdf\Dompdf;
use Dompdf\Options;
use Illuminate\Http\Request;
use Illuminate\Validation\Rule;

/**
 * Exporta los 4 reportes (ejecutivo / sitio / recurso / servicios) en CSV, XLSX
 * y PDF (con imagen corporativa). Lectura: disponible a cualquier rol autenticado.
 */
class ReporteExportController extends Controller
{
    public function export(string $tipo, Request $request)
    {
        $request->merge(['tipo' => $tipo]);
        $v = $request->validate([
            'tipo'    => [Rule::in(['ejecutivo', 'sitio', 'recurso', 'servicios'])],
            'formato' => [Rule::in(['csv', 'xlsx', 'pdf'])],
            'rango'   => ['nullable', Rule::in(['24h', '7d', '30d'])],
            'id'      => ['nullable', 'integer'],
        ]);
        $rango = $v['rango'] ?? '7d';
        $id = isset($v['id']) ? (int) $v['id'] : null;

        $data = ReporteData::construir($tipo, $rango, $id);
        $base = 'reporte_'.$tipo.'_'.$rango.'_'.now()->format('Ymd_Hi');

        return match ($v['formato']) {
            'csv'  => $this->descarga(ReporteExport::csv($data), "$base.csv", 'text/csv; charset=utf-8'),
            'xlsx' => $this->descarga(ReporteExport::xlsx($data), "$base.xlsx",
                          'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            'pdf'  => $this->descarga($this->pdf($data), "$base.pdf", 'application/pdf'),
        };
    }

    private function descarga(string $contenido, string $nombre, string $mime)
    {
        return response($contenido, 200, [
            'Content-Type'        => $mime,
            'Content-Disposition' => 'attachment; filename="'.$nombre.'"',
            'Content-Length'      => (string) strlen($contenido),
        ]);
    }

    private function pdf(array $data): string
    {
        $html = view('reportes.pdf', [
            'data'     => $data,
            'logo'     => $this->logoDataUri(),
            'generado' => now()->format('Y-m-d H:i'),
        ])->render();

        $options = new Options();
        $options->set('isRemoteEnabled', false);
        $options->set('defaultFont', 'DejaVu Sans');
        $options->set('isHtml5ParserEnabled', true);

        $dompdf = new Dompdf($options);
        $dompdf->loadHtml($html);
        $dompdf->setPaper('A4', 'landscape');
        $dompdf->render();

        // Numeración de página en el pie.
        $canvas = $dompdf->getCanvas();
        $font = $dompdf->getFontMetrics()->getFont('DejaVu Sans');
        $canvas->page_text(
            $canvas->get_width() - 120, $canvas->get_height() - 28,
            'Página {PAGE_NUM} de {PAGE_COUNT}', $font, 8, [0.54, 0.58, 0.55]
        );

        return (string) $dompdf->output();
    }

    private function logoDataUri(): ?string
    {
        $ruta = resource_path('branding/logo-simon.png');
        if (! is_file($ruta)) {
            return null;
        }

        return 'data:image/png;base64,'.base64_encode((string) file_get_contents($ruta));
    }
}
