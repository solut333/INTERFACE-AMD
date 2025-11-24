#!/bin/bash

set -e # Encerra o script imediatamente se um comando falhar.

# Este script assume que está sendo executado de dentro da pasta 'services'.
# Detecta o caminho absoluto do projeto (a pasta pai de 'services').
PROJECT_PATH=$(cd "$(dirname "$PWD")" && pwd)
SERVICE_FILE_TEMPLATE="pop-controller.service"
SERVICE_FILE_NAME="pop-controller.service"
SYSTEMD_PATH="/etc/systemd/system"

echo "Caminho do projeto detectado: $PROJECT_PATH"

# Caminho completo para o script de inicialização
BOOT_SCRIPT_PATH="$PROJECT_PATH/apply_on_boot.py"

echo "Configurando o serviço do systemd..."

# Verifica se o script de inicialização existe
if [ ! -f "$BOOT_SCRIPT_PATH" ]; then
    echo "Erro: Script de inicialização '$BOOT_SCRIPT_PATH' não encontrado!"
    exit 1
fi

# Cria um arquivo de serviço temporário com o caminho correto,
# usando 'sed' para substituir o marcador.
sed "s|__EXEC_START_PATH__|$BOOT_SCRIPT_PATH|g" "$SERVICE_FILE_TEMPLATE" > "/tmp/$SERVICE_FILE_NAME"

# Copia o arquivo de serviço configurado para o diretório do systemd
sudo cp "/tmp/$SERVICE_FILE_NAME" "$SYSTEMD_PATH/"

# Limpa o arquivo temporário
rm "/tmp/$SERVICE_FILE_NAME"

# Recarrega o daemon do systemd para reconhecer o novo serviço
sudo systemctl daemon-reload

# Habilita o serviço para iniciar na inicialização
sudo systemctl enable "$SERVICE_FILE_NAME"

echo "Serviço instalado e habilitado com sucesso!"
echo "As configurações salvas serão aplicadas na próxima inicialização."
