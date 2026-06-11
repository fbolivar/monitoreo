#!/usr/bin/env bash
# Genera clave privada + CSR para que tu CA interna (AD Certificate Services)
# firme el certificado de SIMON. Tras firmarlo, instala el .crt y recarga nginx.
# Uso: FQDN=bc360.pnnc.local bash cert_csr.sh
set -euo pipefail
FQDN="${FQDN:-bc360.pnnc.local}"
D=/etc/ssl/monitoreo
install -d "$D"

openssl req -new -newkey rsa:2048 -nodes \
  -keyout "$D/$FQDN.key" \
  -out "$D/$FQDN.csr" \
  -subj "/CN=$FQDN/O=Parques Nacionales Naturales de Colombia/C=CO" \
  -addext "subjectAltName=DNS:$FQDN"
chmod 600 "$D/$FQDN.key"

echo "Clave privada: $D/$FQDN.key   (NO la compartas)"
echo "CSR:           $D/$FQDN.csr"
echo
echo "===== Copia este CSR y fírmalo con tu CA de AD (plantilla 'Web Server') ====="
cat "$D/$FQDN.csr"
echo "============================================================================"
echo
echo "Después:"
echo "  1) Guarda el certificado firmado + la cadena de la CA en:  $D/$FQDN.crt"
echo "  2) Edita /etc/nginx/sites-enabled/monitoreo:"
echo "       ssl_certificate     $D/$FQDN.crt;"
echo "       ssl_certificate_key $D/$FQDN.key;"
echo "       server_name         $FQDN;"
echo "  3) nginx -t && systemctl reload nginx"
echo "Los PCs del dominio ya confían en tu CA (GPO) -> el navegador deja de avisar."
