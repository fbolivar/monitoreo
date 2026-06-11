#!/usr/bin/env bash
echo "== conteo de eventos en el journal =="
J=$(journalctl -u monitoreo-worker --no-pager)
echo "$J" | grep -c "Job alta"            | sed 's/^/  Job alta: /'
echo "$J" | grep -c "Job baja"            | sed 's/^/  Job baja: /'
echo "$J" | grep -c "Chequeo "            | sed 's/^/  Chequeo (INFO): /'
echo "$J" | grep -cE "ERROR|Exception|Traceback|raised an exception" | sed 's/^/  errores: /'
echo "== primeras lineas tras arranque =="
echo "$J" | grep -E "Worker en marcha|Job alta|Job baja|ERROR|Exception|Fallo|raised" | head -30
echo "== ultimas lineas de error/baja =="
echo "$J" | grep -E "Job baja|ERROR|Exception|Traceback|raised an exception|Fallo al chequear" | tail -20
