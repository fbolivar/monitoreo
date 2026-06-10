#!/usr/bin/env bash
echo -n "GET /up      -> "; curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1/up
echo -n "GET /api/me  -> "; curl -s -o /dev/null -w '%{http_code} (esperado 401)\n' http://127.0.0.1/api/me
echo    "cuerpo /api/me:"; curl -s http://127.0.0.1/api/me; echo
echo -n "GET /api/recursos -> "; curl -s -o /dev/null -w '%{http_code} (esperado 401)\n' http://127.0.0.1/api/recursos
echo -n "GET / (sin frontend) -> "; curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1/
