#!/bin/bash

CERT_DIR="../nginx/certs"
DOMAIN="sancho.mapir"

mkdir -p "$CERT_DIR"

openssl req -x509 -nodes -days 365 \
  -newkey rsa:2048 \
  -keyout "$CERT_DIR/key.pem" \
  -out "$CERT_DIR/cert.pem" \
  -subj "/CN=$DOMAIN"

echo "✅ Certificados generados en $CERT_DIR"
