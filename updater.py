#!/usr/bin/env python3
import sys
import os
import subprocess
import time
import zipfile

def log(message):
    print(f"[UPDATER] {message}")

def main():
    if len(sys.argv) < 3:
        log("ERRO: Argumentos insuficientes. Uso: updater.py <zip_path> <install_dir>")
        sys.exit(1)

    zip_path = sys.argv[1]
    install_dir = sys.argv[2]
    main_app_executable = os.path.join(install_dir, "main.py")

    log("Aguardando o aplicativo principal fechar...")
    time.sleep(3)

    log(f"Extraindo atualização de '{zip_path}' para '{install_dir}'...")
    try:
        subprocess.run(f'pkexec --user root unzip -o {zip_path} -d {install_dir}', shell=True, check=True)
        log("Extração concluída com sucesso.")
    except subprocess.CalledProcessError as e:
        log(f"ERRO: Falha ao extrair a atualização. {e}")
        subprocess.Popen([main_app_executable])
        sys.exit(1)

    log("Limpando arquivos temporários...")
    os.remove(zip_path)

    log("Reiniciando o aplicativo...")
    subprocess.Popen([main_app_executable])

if __name__ == "__main__":
    main()