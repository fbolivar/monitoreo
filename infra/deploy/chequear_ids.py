"""Fuerza un chequeo inmediato de los recursos cuyos id se pasan como argumentos."""
import sys

from monitor.config import cargar_settings
from monitor.db import Database
from monitor.runner import ejecutar_chequeo_por_id

s = cargar_settings()
db = Database(s)
for a in sys.argv[1:]:
    try:
        ejecutar_chequeo_por_id(db, s, int(a))
    except Exception as e:  # noqa: BLE001
        print("error chequeando", a, e)
db.close()
print("chequeados:", " ".join(sys.argv[1:]))
