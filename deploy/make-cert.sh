#!/usr/bin/env bash
# Самоподписанный сертификат для стенда в локальной сети: адрес стенда — IP ноутбука.
# Телефон один раз покажет предупреждение о сертификате, его нужно принять.
set -euo pipefail
cd "$(dirname "$0")"
IP="${1:-$(ipconfig getifaddr en0 2>/dev/null || hostname -I | awk '{print $1}')}"
mkdir -p certs
openssl req -x509 -newkey rsa:2048 -nodes -days 30 \
  -keyout certs/stand.key -out certs/stand.crt \
  -subj "/CN=FamilyQuest стенд" \
  -addext "subjectAltName=IP:${IP},DNS:localhost"
echo "Сертификат для https://${IP} готов"
