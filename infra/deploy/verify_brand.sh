#!/usr/bin/env bash
echo -n "GET /            : "; curl -sk -o /dev/null -w '%{http_code}\n' https://127.0.0.1/
echo -n "title            : "; curl -sk https://127.0.0.1/ | grep -o '<title>[^<]*</title>'
echo -n "logo-simon.png   : "; curl -sk -o /dev/null -w '%{http_code}  %{size_download} bytes\n' https://127.0.0.1/logo-simon.png
echo -n "favicon-64.png   : "; curl -sk -o /dev/null -w '%{http_code}  %{size_download} bytes\n' https://127.0.0.1/favicon-64.png
echo -n "fuentes (link)   : "; curl -sk https://127.0.0.1/ | grep -o 'Montserrat' | head -1
