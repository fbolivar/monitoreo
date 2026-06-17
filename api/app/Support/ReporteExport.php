<?php

namespace App\Support;

use PhpOffice\PhpSpreadsheet\Spreadsheet;
use PhpOffice\PhpSpreadsheet\Style\Alignment;
use PhpOffice\PhpSpreadsheet\Style\Fill;
use PhpOffice\PhpSpreadsheet\Writer\Xlsx;

/** Renderiza la estructura normalizada de ReporteData a CSV y XLSX. */
class ReporteExport
{
    /** CSV (UTF-8 con BOM): KPIs + cada tabla, separados por líneas en blanco. */
    public static function csv(array $data): string
    {
        $out = [];
        $out[] = [self::limpia($data['titulo'] ?? '')];
        $out[] = [self::limpia($data['subtitulo'] ?? '')];
        $out[] = [];
        if (! empty($data['kpis'])) {
            $out[] = ['Indicador', 'Valor'];
            foreach ($data['kpis'] as $k) {
                $out[] = [$k['label'], (string) $k['valor']];
            }
            $out[] = [];
        }
        foreach ($data['tablas'] ?? [] as $t) {
            $out[] = [self::limpia($t['titulo'])];
            $out[] = $t['columnas'];
            foreach ($t['filas'] as $f) {
                $out[] = array_map(fn ($c) => (string) $c, $f);
            }
            $out[] = [];
        }

        $csv = implode("\r\n", array_map(
            fn ($fila) => implode(',', array_map(
                fn ($c) => '"'.str_replace('"', '""', (string) $c).'"', $fila)),
            $out));

        return "\u{FEFF}".$csv;
    }

    /** XLSX: hoja "Resumen" (título + KPIs) + una hoja por tabla con cabecera con estilo. */
    public static function xlsx(array $data): string
    {
        $libro = new Spreadsheet();
        $verde = '2E7D3A';

        // Hoja resumen
        $hoja = $libro->getActiveSheet();
        $hoja->setTitle('Resumen');
        $hoja->setCellValue('A1', $data['titulo'] ?? 'Reporte');
        $hoja->getStyle('A1')->getFont()->setBold(true)->setSize(14);
        $hoja->setCellValue('A2', $data['subtitulo'] ?? '');
        $hoja->getStyle('A2')->getFont()->setSize(9)->getColor()->setRGB('666666');
        $fila = 4;
        if (! empty($data['kpis'])) {
            $hoja->setCellValue("A$fila", 'Indicador'); $hoja->setCellValue("B$fila", 'Valor');
            self::cabecera($hoja, "A$fila:B$fila", $verde);
            $fila++;
            foreach ($data['kpis'] as $k) {
                $hoja->setCellValue("A$fila", $k['label']);
                $hoja->setCellValue("B$fila", (string) $k['valor']);
                $fila++;
            }
        }
        foreach (['A', 'B'] as $col) {
            $hoja->getColumnDimension($col)->setAutoSize(true);
        }

        // Una hoja por tabla
        $usadas = ['Resumen' => true];
        foreach ($data['tablas'] ?? [] as $i => $t) {
            $nombre = self::nombreHoja($t['titulo'], $i, $usadas);
            $h = $libro->createSheet();
            $h->setTitle($nombre);
            $h->setCellValue('A1', $t['titulo']);
            $h->getStyle('A1')->getFont()->setBold(true)->setSize(12);

            $r = 3;
            $cols = $t['columnas'];
            $ult = self::colLetra(count($cols));
            foreach ($cols as $j => $c) {
                $h->setCellValueByColumnAndRow($j + 1, $r, $c);
            }
            self::cabecera($h, "A$r:$ult$r", $verde);
            $r++;
            foreach ($t['filas'] as $f) {
                foreach (array_values($f) as $j => $c) {
                    $h->setCellValueByColumnAndRow($j + 1, $r, is_numeric($c) ? $c + 0 : (string) $c);
                }
                $r++;
            }
            for ($j = 1; $j <= count($cols); $j++) {
                $h->getColumnDimensionByColumn($j)->setAutoSize(true);
            }
        }

        $libro->setActiveSheetIndex(0);
        ob_start();
        (new Xlsx($libro))->save('php://output');

        return (string) ob_get_clean();
    }

    private static function cabecera($hoja, string $rango, string $rgb): void
    {
        $st = $hoja->getStyle($rango);
        $st->getFont()->setBold(true)->getColor()->setRGB('FFFFFF');
        $st->getFill()->setFillType(Fill::FILL_SOLID)->getStartColor()->setRGB($rgb);
        $st->getAlignment()->setHorizontal(Alignment::HORIZONTAL_LEFT);
    }

    private static function colLetra(int $n): string
    {
        return \PhpOffice\PhpSpreadsheet\Cell\Coordinate::stringFromColumnIndex($n);
    }

    private static function nombreHoja(string $titulo, int $i, array &$usadas): string
    {
        $base = preg_replace('/[\\\\\\/\\?\\*\\[\\]:]/', ' ', $titulo);
        $base = trim(mb_substr($base, 0, 28));
        $n = $base !== '' ? $base : 'Tabla '.($i + 1);
        $c = $n;
        $k = 2;
        while (isset($usadas[$c])) { $c = mb_substr($n, 0, 26).' '.$k++; }
        $usadas[$c] = true;

        return $c;
    }

    private static function limpia(string $s): string
    {
        return str_replace(["\r", "\n"], ' ', $s);
    }
}
