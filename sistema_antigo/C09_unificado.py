import subprocess
from datetime import datetime
import os
import sys

sys.stdout = open("log_C09_unificado.txt", "a", encoding="utf-8")
sys.stderr = sys.stdout


def main():
    # Período: do primeiro dia do mês até hoje
    hoje = datetime.today()
    data_inicial = hoje.replace(day=1).strftime("%d/%m/%Y")
    data_final   = hoje.strftime("%d/%m/%Y")

    # Exporta para os scripts originais como variáveis de ambiente
    os.environ["DATA_INICIAL"] = data_inicial
    os.environ["DATA_FINAL"]   = data_final

    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Iniciando RRP: {data_inicial} -> {data_final}")

    print(f"\n=== RRP: {data_inicial} - {data_final} ===")
    result_rrp = subprocess.run(["python", "C09_RRP.py"])
    if result_rrp.returncode != 0:
        print("Erro no processamento do RRP!")
        return

    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Iniciando TLS: {data_inicial} -> {data_final}")
    print(f"\n=== RRP: {data_inicial} - {data_final} ===")
    result_tls = subprocess.run(["python", "C09_TLS.py"])
    if result_tls.returncode != 0:
        print("Erro no processamento do TLS!")
        return

    print("\n=== PROCESSO FINALIZADO COM SUCESSO ===")

if __name__ == "__main__":
    main()
