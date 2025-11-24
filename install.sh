#!/bin/bash

# Garante que o script está sendo executado com privilégios de root
if [ "$EUID" -ne 0 ]; then 
  echo "Por favor, execute este script como root ou com sudo."
  exit 1
fi

set -e # Encerra o script se um comando falhar

APP_DIR="/opt/pop-os-controller"
LAUNCHER_PATH="/usr/share/applications/pop-os-controller.desktop"

echo "Iniciando a instalação do GPU Controller..."

# 1. Instalar dependências do sistema
echo "--> Verificando dependências do sistema..."
apt-get update
apt-get install -y python3-pip python3-tk

# 2. Criar diretório da aplicação
echo "--> Criando diretório em $APP_DIR..."
mkdir -p "$APP_DIR"

# 3. Copiar arquivos do projeto
echo "--> Copiando arquivos da aplicação..."
cp -r ./* "$APP_DIR/"

# 4. Instalar dependências do Python
echo "--> Instalando dependências do Python via pip..."
pip3 install -r "$APP_DIR/requirements.txt"

# 5. Instalar o lançador do menu de aplicativos
echo "--> Instalando o lançador de aplicativos..."
cp "$APP_DIR/pop-os-controller.desktop" "$LAUNCHER_PATH"
chmod +x "$APP_DIR/run.sh"

# 6. Instalar o serviço do systemd para persistência
echo "--> Configurando o serviço de inicialização..."
# Modifica o service file para usar o caminho absoluto correto
sed -i "s|__EXEC_START_PATH__|$APP_DIR/apply_on_boot.py|g" "$APP_DIR/services/pop-controller.service"
cp "$APP_DIR/services/pop-controller.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable pop-controller.service

echo ""
echo "Instalação concluída com sucesso!"
echo "Você pode encontrar 'GPU Controller' no seu menu de aplicativos."
