#!/bin/bash

CONF_PATH=$(realpath ../nginx/rosbridge_proxy.conf)

echo "🔧 Usando config: $CONF_PATH"
sudo nginx -c "$CONF_PATH"

echo "🚀 Nginx lanzado con rosbridge_proxy.conf"
