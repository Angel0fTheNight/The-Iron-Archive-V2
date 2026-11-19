#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_trava_simultanea.py - Teste de travamento exclusivo do download_seguro.py

Inicia dois processos de download para o MESMO destino e comprova que
apenas um obtém a trava exclusiva (.lock). O outro deve falhar com
trava_ocupada e não produzir arquivo final corrompido.

Nenhum checkpoint real é baixado. Arquivo fictício de 85 bytes.
"""

import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
TEST_ROOT = SCRIPTS_DIR / "test_trava_simultanea"
SERVER_FILES = TEST_ROOT / "server_files"
WORK_DIR = TEST_ROOT / "work"

DOWNLOADER = SCRIPTS_DIR / "download_seguro.py"
PYTHON = sys.executable

# Arquivo fictício de 85 bytes (mesmo mini.safetensors da outra suíte)
TENSOR = b"\x00\x01\x02\x03\x04\x05\x06\x07"
meta = {"tensor1": {"dtype": "F32", "shape": [1], "data_offsets": [0, len(TENSOR)]}}
# Calcula o header com offsets finais (o tamanho do header depende dos valores dos offsets).
header = json.dumps(meta).encode("utf-8")
for _ in range(3):
    header_len = len(header)
    data_start = 8 + header_len
    # Offsets são RELATIVOS ao início da região de dados
    meta["tensor1"]["data_offsets"] = [0, len(TENSOR)]
    novo_header = json.dumps(meta).encode("utf-8")
    if len(novo_header) == header_len:
        header = novo_header
        break
    header = novo_header
FILE_CONTENT = struct.pack("<Q", len(header)) + header + TENSOR
FILE_SIZE = len(FILE_CONTENT)
FILE_SHA256 = hashlib.sha256(FILE_CONTENT).hexdigest()


class SlowHandler(BaseHTTPRequestHandler):
    """Responde após 3s para garantir que o segure o lock enquanto o outro tenta."""
    server_version = "SlowTest/1.0"

    def log_message(self, format, *args):
        return

    def do_GET(self):
        time.sleep(3)
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(FILE_SIZE))
        self.end_headers()
        self.wfile.write(FILE_CONTENT)


def start_server(port):
    server = HTTPServer(("127.0.0.1", port), SlowHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def main():
    shutil.rmtree(TEST_ROOT, ignore_errors=True)
    TEST_ROOT.mkdir(parents=True, exist_ok=True)
    SERVER_FILES.mkdir(parents=True, exist_ok=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    (SERVER_FILES / "modelo.safetensors").write_bytes(FILE_CONTENT)

    server = start_server(0)
    port = server.server_address[1]
    time.sleep(0.5)
    base = f"http://127.0.0.1:{port}"

    out_path = WORK_DIR / "trava.safetensors"
    part_path = Path(str(out_path) + ".part")
    lock_path = Path(str(out_path) + ".lock")

    cmd = [
        PYTHON, str(DOWNLOADER),
        "--url", f"{base}/modelo.safetensors",
        "--out", str(out_path),
        "--size", str(FILE_SIZE),
        "--sha256", FILE_SHA256,
        "--max-attempts", "1",
        "--timeout", "10",
        "--min-free-disk", "0",
    ]

    # Inicia dois processos quase simultaneamente para o MESMO destino.
    p1 = subprocess.Popen(cmd, cwd=str(SCRIPTS_DIR), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(0.1)
    p2 = subprocess.Popen(cmd, cwd=str(SCRIPTS_DIR), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    r1 = p1.wait(timeout=30)
    r2 = p2.wait(timeout=30)

    print(f"Processo 1 rc={r1} | Processo 2 rc={r2}")
    p1_out, p1_err = p1.communicate()
    p2_out, p2_err = p2.communicate()
    print(f"STDOUT p1: {p1_out[:500] if p1_out else ''}")
    print(f"STDOUT p2: {p2_out[:500] if p2_out else ''}")
    print(f"STDERR p1: {p1_err[:500] if p1_err else ''}")
    print(f"STDERR p2: {p2_err[:500] if p2_err else ''}")

    final_existe = out_path.exists()
    part_existe = part_path.exists()
    lock_existe = lock_path.exists()

    print(f"Final existe: {final_existe} | .part existe: {part_existe} | .lock existe: {lock_existe}")
    if final_existe:
        print(f"Conteúdo final correto: {out_path.read_bytes() == FILE_CONTENT}")
        print(f"SHA-256 final: {hashlib.sha256(out_path.read_bytes()).hexdigest()}")

    server.shutdown()

    # Critério de sucesso:
    # - Exatamente um dos dois processos obteve a trava (rc=0) ou, no mínimo,
    #   um falhou por trava_ocupada e o outro completou com sucesso.
    # - O arquivo final, se existir, deve ser o correto (não corrompido).
    # - Nunca deve haver dois arquivos finais válidos.
    sucessos = sum(1 for r in (r1, r2) if r == 0)
    falhas_trava = 0
    for saida in (p1_out, p2_out):
        if "trava_ocupada" in (saida or ""):
            falhas_trava += 1

    print(f"Sucessos: {sucessos} | Falhas por trava_ocupada: {falhas_trava}")

    ok = (
        sucessos == 1 and falhas_trava == 1 and
        final_existe and out_path.read_bytes() == FILE_CONTENT and
        not part_existe and not lock_existe
    )
    print(f"RESULTADO: {'OK' if ok else 'FALHA'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
