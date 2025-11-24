import subprocess
import logging
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

IS_AUTHENTICATED = False

def run_command(command):
    global IS_AUTHENTICATED

    if 'sudo' in command and not IS_AUTHENTICATED:
        try:
            logging.info("Solicitando privilégios de root pela primeira vez...")
            subprocess.run('pkexec --user root whoami', shell=True, check=True, capture_output=True)
            IS_AUTHENTICATED = True
            logging.info("Autenticação bem-sucedida. A senha não será solicitada novamente nesta sessão.")
        except subprocess.CalledProcessError:
            logging.error("Falha na autenticação. Não é possível executar comandos com privilégios de root.")
            return None

    try:
        logging.info(f"Executando comando: {command}")
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            capture_output=True,
            text=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logging.error(f"Erro ao executar comando: {command}\nErro: {e.stderr.strip()}")
        return None
