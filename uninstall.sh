#!/bin/bash

if [ "$EUID" -ne 0 ]; then 
  exit 1
fi

set -e

echo "--- Iniciando desinstalação do GPU Controller ---"

APP_DIR="/opt/pop-os-controller"
LAUNCHER_PATH="/usr/share/applications/pop-os-controller.desktop"
SERVICE_FILE="/etc/systemd/system/pop-controller.service"

echo "[LOG] Verificando e parando o serviço systemd..."
if systemctl is-active --quiet pop-controller.service; then
    echo "[LOG] Serviço 'pop-controller.service' está ativo. Parando..."
    systemctl stop pop-controller.service
else
    echo "[LOG] Serviço 'pop-controller.service' já estava parado."
fi

echo "[LOG] Verificando e desabilitando o serviço systemd..."
if systemctl is-enabled --quiet pop-controller.service; then
    echo "[LOG] Serviço 'pop-controller.service' está habilitado. Desabilitando..."
    systemctl disable pop-controller.service
else
    echo "[LOG] Serviço 'pop-controller.service' já estava desabilitado."
fi

echo "[LOG] Removendo arquivo de serviço..."
if [ -f "$SERVICE_FILE" ]; then
    rm -f "$SERVICE_FILE"
    echo "[LOG] Arquivo '$SERVICE_FILE' removido."
    systemctl daemon-reload
    echo "[LOG] Systemd reloaded."
else
    echo "[LOG] Arquivo de serviço '$SERVICE_FILE' não encontrado. Pulando."
fi

echo "[LOG] Removendo o atalho do menu de aplicativos..."
if [ -f "$LAUNCHER_PATH" ]; then
    rm -f "$LAUNCHER_PATH"
    echo "[LOG] Atalho '$LAUNCHER_PATH' removido."
else
    echo "[LOG] Atalho '$LAUNCHER_PATH' não encontrado. Pulando."
fi

echo "[LOG] Removendo o diretório da aplicação..."
if [ -d "$APP_DIR" ]; then
    rm -rf "$APP_DIR"
    echo "[LOG] Diretório '$APP_DIR' removido."
else
    echo "[LOG] Diretório da aplicação '$APP_DIR' não encontrado. Pulando."
fi

echo "--- Desinstalação concluída com sucesso! ---"
