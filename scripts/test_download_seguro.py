#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_download_seguro.py - Suíte de testes do download_seguro.py

Cria arquivos pequenos e fictícios dentro de D:/TheIronArchive_V2/scripts/
e simula respostas HTTP (200, 206 válido, Content-Range incorreto, truncado,
hash incorreto, excesso de tamanho) usando um servidor HTTP local embutido.

NENHUM checkpoint real é baixado. Todos os testes ficam restritos à V2.
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
TEST_ROOT = SCRIPTS_DIR / "test_download_seguro"
SERVER_FILES = TEST_ROOT / "server_files"
WORK_DIR = TEST_ROOT / "work"
LOGS_DIR = SCRIPTS_DIR / "logs"
SERVER_FILES.mkdir(parents=True, exist_ok=True)
WORK_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

DOWNLOADER = SCRIPTS_DIR / "download_seguro.py"
PYTHON = sys.executable

# Arquivo "modelo" pequeno e fictício (1024 bytes)
MODEL_SIZE = 1024
MODEL_CONTENT = bytes((i % 256) for i in range(MODEL_SIZE))
MODEL_SHA256 = hashlib.sha256(MODEL_CONTENT).hexdigest()

# Mini-safetensors válido para testar estrutura + sucesso
def make_mini_safetensors(tensor_data: bytes, path: Path, incluir_metadata=True):
    meta = {"tensor1": {"dtype": "F32", "shape": [1], "data_offsets": [0, len(tensor_data)]}}
    if incluir_metadata:
        meta["__metadata__"] = {"format": "pt", "hash": "abc123"}
    header = json.dumps(meta).encode("utf-8")
    header_len = len(header)
    data_start = 8 + header_len
    # Offsets são RELATIVOS ao início da região de dados (após 8 + header_len)
    meta["tensor1"]["data_offsets"] = [0, len(tensor_data)]
    header = json.dumps(meta).encode("utf-8")
    header_len = len(header)
    with open(path, "wb") as f:
        f.write(struct.pack("<Q", len(header)))
        f.write(header)
        f.write(tensor_data)

MINI_TENSOR = b"\x00\x01\x02\x03\x04\x05\x06\x07"  # 8 bytes
MINI_PATH = SERVER_FILES / "mini.safetensors"
make_mini_safetensors(MINI_TENSOR, MINI_PATH, incluir_metadata=True)
MINI_SIZE = MINI_PATH.stat().st_size
MINI_SHA256 = hashlib.sha256(MINI_PATH.read_bytes()).hexdigest()

# Mini-safetensors com __metadata__ INVÁLIDO (tem data_offsets - não deve ser aceito)
def make_mini_metadata_invalido(path: Path):
    meta = {
        "__metadata__": {"format": "pt", "data_offsets": [0, 10]},
        "tensor1": {"dtype": "F32", "shape": [1], "data_offsets": [0, 8]},
    }
    header = json.dumps(meta).encode("utf-8")
    header_len = len(header)
    data_start = 8 + header_len
    # Offsets são RELATIVOS
    meta["tensor1"]["data_offsets"] = [0, 8]
    header = json.dumps(meta).encode("utf-8")
    header_len = len(header)
    with open(path, "wb") as f:
        f.write(struct.pack("<Q", len(header)))
        f.write(header)
        f.write(b"\x00" * 8)


MINI_META_INVALIDO_PATH = SERVER_FILES / "mini_metadata_invalido.safetensors"
make_mini_metadata_invalido(MINI_META_INVALIDO_PATH)
MINI_META_INVALIDO_SIZE = MINI_META_INVALIDO_PATH.stat().st_size
MINI_META_INVALIDO_SHA256 = hashlib.sha256(MINI_META_INVALIDO_PATH.read_bytes()).hexdigest()

# Mini-safetensors com cabeçalho JSON MALFORMADO
MINI_MALFORMADO_PATH = SERVER_FILES / "mini_cabecalho_malformado.safetensors"
MINI_MALFORMADO_HEADER = b"{"  # JSON incompleto
MINI_MALFORMADO_DATA = b"\x00" * 8
MINI_MALFORMADO_CONTENT = struct.pack("<Q", len(MINI_MALFORMADO_HEADER)) + MINI_MALFORMADO_HEADER + MINI_MALFORMADO_DATA
MINI_MALFORMADO_PATH.write_bytes(MINI_MALFORMADO_CONTENT)
MINI_MALFORMADO_SIZE = len(MINI_MALFORMADO_CONTENT)
MINI_MALFORMADO_SHA256 = hashlib.sha256(MINI_MALFORMADO_CONTENT).hexdigest()

# Mini-safetensors com tensores sobrepostos
def make_mini_sobreposicao(path: Path):
    meta = {
        "tensor1": {"dtype": "F32", "shape": [1], "data_offsets": [0, 10]},
        "tensor2": {"dtype": "F32", "shape": [1], "data_offsets": [5, 15]},
    }
    header = json.dumps(meta).encode("utf-8")
    header_len = len(header)
    data_start = 8 + header_len
    # Offsets são RELATIVOS
    meta["tensor1"]["data_offsets"] = [0, 10]
    meta["tensor2"]["data_offsets"] = [5, 15]
    header = json.dumps(meta).encode("utf-8")
    header_len = len(header)
    with open(path, "wb") as f:
        f.write(struct.pack("<Q", len(header)))
        f.write(header)
        f.write(b"\x00" * 15)


MINI_SOBREPOSICAO_PATH = SERVER_FILES / "mini_sobreposicao.safetensors"
make_mini_sobreposicao(MINI_SOBREPOSICAO_PATH)
MINI_SOBREPOSICAO_SIZE = MINI_SOBREPOSICAO_PATH.stat().st_size
MINI_SOBREPOSICAO_SHA256 = hashlib.sha256(MINI_SOBREPOSICAO_PATH.read_bytes()).hexdigest()

MODELO_PATH = SERVER_FILES / "modelo.bin"
MODELO_PATH.write_bytes(MODEL_CONTENT)

# ---------------------------------------------------------------------------
# Servidor HTTP fictício
# ---------------------------------------------------------------------------
class FakeHandler(BaseHTTPRequestHandler):
    server_version = "FakeTest/1.0"

    def log_message(self, format, *args):
        return  # silencioso

    def _send_range(self, path: Path, start: int, end: int, total: int, status=206):
        data = path.read_bytes()
        slice_data = data[start:end + 1]
        self.send_response(status)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Range", f"bytes {start}-{end}/{total}")
        self.send_header("Content-Length", str(len(slice_data)))
        self.end_headers()
        self.wfile.write(slice_data)

    def _send_full(self, path: Path, status=200):
        data = path.read_bytes()
        self.send_response(status)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url_path = self.path.split("?")[0]
        rng = self.headers.get("Range")

        # --- Cenários especiais ------------------------------------------------
        if url_path == "/bad-range":
            # Responde 206 mas com Content-Range de início diferente do solicitado
            data = MINI_PATH.read_bytes()
            self.send_response(206)
            self.send_header("Content-Range", f"bytes 100-999/{MINI_SIZE}")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        if url_path == "/http200-only":
            # Ignora Range, responde sempre 200 com o arquivo completo
            self._send_full(MINI_PATH, status=200)
            return

        if url_path == "/truncated":
        # Responde 206 com Content-Range completo, mas envia apenas metade dos bytes
            total = MINI_SIZE
            half = total // 2
            data = MINI_PATH.read_bytes()[:half]
            self.send_response(206)
            self.send_header("Content-Range", f"bytes 0-{total - 1}/{total}")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        # --- Cenário normal: modelo.bin --------------------------------------
        if url_path == "/modelo.bin":
            data = MODELO_PATH.read_bytes()
            if rng:
                import re as _re
                m = _re.match(r"bytes=(\d+)-", rng.strip())
                if m:
                    start = int(m.group(1))
                    end = min(start + 511, len(data) - 1)
                    self.send_response(206)
                    self.send_header("Content-Type", "application/octet-stream")
                    self.send_header("Content-Range", f"bytes {start}-{end}/{len(data)}")
                    self.send_header("Content-Length", str(end - start + 1))
                    self.end_headers()
                    self.wfile.write(data[start:end + 1])
                    return
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        # --- Cenário normal: mini.safetensors --------------------------------
        if url_path == "/mini.safetensors":
            data = MINI_PATH.read_bytes()
            if rng:
                import re as _re
                m = _re.match(r"bytes=(\d+)-", rng.strip())
                if m:
                    start = int(m.group(1))
                    end = min(start + 63, len(data) - 1)
                    self.send_response(206)
                    self.send_header("Content-Range", f"bytes {start}-{end}/{len(data)}")
                    self.send_header("Content-Length", str(end - start + 1))
                    self.end_headers()
                    self.wfile.write(data[start:end + 1])
                    return
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        # --- Arquivos de estrutura para teste do validador ---------------------
        if url_path == "/mini_metadata_invalido.safetensors":
            data = MINI_META_INVALIDO_PATH.read_bytes()
            if rng:
                import re as _re
                m = _re.match(r"bytes=(\d+)-", rng.strip())
                if m:
                    start = int(m.group(1))
                    end = min(start + 63, len(data) - 1)
                    self.send_response(206)
                    self.send_header("Content-Type", "application/octet-stream")
                    self.send_header("Content-Range", f"bytes {start}-{end}/{len(data)}")
                    self.send_header("Content-Length", str(end - start + 1))
                    self.end_headers()
                    self.wfile.write(data[start:end + 1])
                    return
            self._send_full(MINI_META_INVALIDO_PATH, status=200)
            return

        if url_path == "/mini_cabecalho_malformado.safetensors":
            data = MINI_MALFORMADO_PATH.read_bytes()
            self._send_full(MINI_MALFORMADO_PATH, status=200)
            return

        if url_path == "/mini_sobreposicao.safetensors":
            data = MINI_SOBREPOSICAO_PATH.read_bytes()
            if rng:
                import re as _re
                m = _re.match(r"bytes=(\d+)-", rng.strip())
                if m:
                    start = int(m.group(1))
                    end = min(start + 63, len(data) - 1)
                    self.send_response(206)
                    self.send_header("Content-Type", "application/octet-stream")
                    self.send_header("Content-Range", f"bytes {start}-{end}/{len(data)}")
                    self.send_header("Content-Length", str(end - start + 1))
                    self.end_headers()
                    self.wfile.write(data[start:end + 1])
                    return
            self._send_full(MINI_SOBREPOSICAO_PATH, status=200)
            return

        # --- Excesso de tamanho: arquivo maior que --size ---------------------
        if url_path == "/oversized.bin":
            data = b"\x00" * (MODEL_SIZE + 500)
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        self.send_response(404)
        self.end_headers()


def start_server(port):
    server = HTTPServer(("127.0.0.1", port), FakeHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def run_downloader(url, out_path, size_expected, sha_expected, extra_args=None):
    cmd = [
        PYTHON, str(DOWNLOADER),
        "--url", url,
        "--out", str(out_path),
        "--size", str(size_expected),
        "--sha256", sha_expected,
        "--max-attempts", "2",
        "--timeout", "10",
        "--min-free-disk", "0",  # testes locais: não bloquear por disco
    ]
    if extra_args:
        cmd.extend(extra_args)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        if r.stdout.strip():
            print(f"[DOWNLOADER STDOUT] {r.stdout.strip()}")
        if r.stderr.strip() and "DeprecationWarning" not in r.stderr:
            print(f"[DOWNLOADER STDERR] {r.stderr.strip()}")
    return r


def limpar(caminho: Path):
    if caminho.exists():
        if caminho.is_dir():
            shutil.rmtree(caminho, ignore_errors=True)
        else:
            caminho.unlink(missing_ok=True)


def main():
    limpar(TEST_ROOT)
    TEST_ROOT.mkdir(parents=True, exist_ok=True)
    SERVER_FILES.mkdir(parents=True, exist_ok=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    # Recriar mini.safetensors (pode ter sido apagado em runs anteriores)
    make_mini_safetensors(MINI_TENSOR, MINI_PATH, incluir_metadata=True)
    make_mini_metadata_invalido(MINI_META_INVALIDO_PATH)
    MINI_MALFORMADO_PATH.write_bytes(MINI_MALFORMADO_CONTENT)
    make_mini_sobreposicao(MINI_SOBREPOSICAO_PATH)

    server = start_server(0)
    port = server.server_address[1]
    time.sleep(0.5)
    base = f"http://127.0.0.1:{port}"

    resultados = []

    def registrar(nome, ok, detalhe=""):
        resultados.append((nome, ok, detalhe))
        status = "OK" if ok else "FALHA"
        print(f"[{status}] {nome} {detalhe}")

    # ---------------------------------------------------------------
    # Cenário 1: download válido do zero (200) -> sucesso
    # ---------------------------------------------------------------
    out = WORK_DIR / "c1_valido.safetensors"
    limpar(out); limpar(Path(str(out) + ".part"))
    r = run_downloader(f"{base}/mini.safetensors", out, MINI_SIZE, MINI_SHA256)
    registrar("C1 download válido (200)", r.returncode == 0 and out.exists() and not Path(str(out) + ".part").exists(),
              f"rc={r.returncode}")

    # ---------------------------------------------------------------
    # Cenário 2: HTTP 200 em retomada (.part parcial existe) -> não append
    # ---------------------------------------------------------------
    out = WORK_DIR / "c2_200_retomada.safetensors"
    part = Path(str(out) + ".part")
    limpar(out); limpar(part)
    part.write_bytes(b"\x00" * 100)  # parcial simulado
    r = run_downloader(f"{base}/http200-only", out, MINI_SIZE, MINI_SHA256)
    registrar("C2 HTTP 200 na retomada (não append)", r.returncode != 0 and not out.exists() and part.exists(),
              f"rc={r.returncode}, part_existe={part.exists()}")

    # ---------------------------------------------------------------
    # Cenário 3: Content-Range incorreto (206 com início errado) -> rejeita
    # ---------------------------------------------------------------
    out = WORK_DIR / "c3_bad_range.safetensors"
    limpar(out); limpar(Path(str(out) + ".part"))
    r = run_downloader(f"{base}/bad-range", out, MINI_SIZE, MINI_SHA256)
    registrar("C3 Content-Range incorreto", r.returncode != 0 and not out.exists(),
              f"rc={r.returncode}")

    # ---------------------------------------------------------------
    # Cenário 4: arquivo truncado (servidor encerra antes do total) -> falha
    # ---------------------------------------------------------------
    out = WORK_DIR / "c4_truncado.safetensors"
    limpar(out); limpar(Path(str(out) + ".part"))
    r = run_downloader(f"{base}/truncated", out, MINI_SIZE, MINI_SHA256)
    registrar("C4 download truncado", r.returncode != 0 and not out.exists(),
              f"rc={r.returncode}")

    # ---------------------------------------------------------------
    # Cenário 5: hash incorreto (--sha256 errado) -> não renomeia
    # ---------------------------------------------------------------
    out = WORK_DIR / "c5_hash_errado.safetensors"
    limpar(out); limpar(Path(str(out) + ".part"))
    r = run_downloader(f"{base}/mini.safetensors", out, MINI_SIZE, "0" * 64)
    registrar("C5 SHA-256 incorreto", r.returncode != 0 and not out.exists(),
              f"rc={r.returncode}")

    # ---------------------------------------------------------------
    # Cenário 6: excesso de tamanho (arquivo > --size) -> aborta
    # ---------------------------------------------------------------
    out = WORK_DIR / "c6_excesso.safetensors"
    limpar(out); limpar(Path(str(out) + ".part"))
    r = run_downloader(f"{base}/oversized.bin", out, MODEL_SIZE, MODEL_SHA256)
    registrar("C6 excesso de tamanho", r.returncode != 0 and not out.exists(),
              f"rc={r.returncode}")

    # ---------------------------------------------------------------
    # Cenário 7: checkpoint final já existe -> não sobrescreve
    # ---------------------------------------------------------------
    out = WORK_DIR / "c7_existente.safetensors"
    out.write_bytes(b"arquivo preexistente")
    r = run_downloader(f"{base}/mini.safetensors", out, MINI_SIZE, MINI_SHA256)
    registrar("C7 final existente (não sobrescrever)", r.returncode != 0 and out.read_bytes() == b"arquivo preexistente",
              f"rc={r.returncode}")

    # ---------------------------------------------------------------
    # Cenário 8: .part com tamanho oficial mas inválido -> não renomeia
    # ---------------------------------------------------------------
    out = WORK_DIR / "c8_part_invalido.safetensors"
    part = Path(str(out) + ".part")
    limpar(out); limpar(part)
    # Grava exatamente size_expected bytes, mas lixo (não é o mini válido)
    part.write_bytes(b"\x00" * MINI_SIZE)
    r = run_downloader(f"{base}/mini.safetensors", out, MINI_SIZE, MINI_SHA256)
    registrar("C8 .part oficial mas inválido", r.returncode != 0 and not out.exists() and part.exists(),
              f"rc={r.returncode}")

    # ---------------------------------------------------------------
    # Cenário 9: .part pré-existente válido (tamanho oficial + hash ok) -> renomeia sem baixar
    # ---------------------------------------------------------------
    out = WORK_DIR / "c9_part_valido.safetensors"
    part = Path(str(out) + ".part")
    limpar(out); limpar(part)
    part.write_bytes(MINI_PATH.read_bytes())  # cópia válida
    r = run_downloader(f"{base}/mini.safetensors", out, MINI_SIZE, MINI_SHA256)
    registrar("C9 .part pré-existente válido (renomeia)", r.returncode == 0 and out.exists() and not part.exists(),
              f"rc={r.returncode}")

    # ---------------------------------------------------------------
    # Cenário 10: resumo com 206 válido (baixar .part em duas partes)
    # ---------------------------------------------------------------
    out = WORK_DIR / "c10_resumo.safetensors"
    limpar(out); limpar(Path(str(out) + ".part"))
    # Primeira parte: forçar parada no meio criando um servidor que responde só metade?
    # Simulado: baixar completo de uma vez já testado em C1. Aqui testamos que
    # um .part parcial + URL normal retoma corretamente.
    part = Path(str(out) + ".part")
    part.write_bytes(MINI_PATH.read_bytes()[:64])  # 64 bytes válidos do início
    r = run_downloader(f"{base}/mini.safetensors", out, MINI_SIZE, MINI_SHA256)
    registrar("C10 retomada de .part parcial com 206", r.returncode == 0 and out.exists() and not part.exists(),
              f"rc={r.returncode}")

    # ---------------------------------------------------------------
    # Cenário 11: __metadata__ legítimo no cabeçalho -> deve ser aceito
    # ---------------------------------------------------------------
    out = WORK_DIR / "c11_metadata_valido.safetensors"
    limpar(out); limpar(Path(str(out) + ".part"))
    r = run_downloader(f"{base}/mini.safetensors", out, MINI_SIZE, MINI_SHA256)
    registrar("C11 __metadata__ legítimo aceito", r.returncode == 0 and out.exists(),
              f"rc={r.returncode}")

    # ---------------------------------------------------------------
    # Cenário 12: __metadata__ com data_offsets (inválido) -> rejeita
    # ---------------------------------------------------------------
    out = WORK_DIR / "c12_metadata_invalido.safetensors"
    limpar(out); limpar(Path(str(out) + ".part"))
    r = run_downloader(f"{base}/mini_metadata_invalido.safetensors", out, MINI_META_INVALIDO_SIZE, MINI_META_INVALIDO_SHA256)
    registrar("C12 __metadata__ com data_offsets rejeitado", r.returncode != 0 and not out.exists(),
              f"rc={r.returncode}")

    # ---------------------------------------------------------------
    # Cenário 13: cabeçalho JSON malformado -> rejeita
    # ---------------------------------------------------------------
    out = WORK_DIR / "c13_cabecalho_malformado.safetensors"
    limpar(out); limpar(Path(str(out) + ".part"))
    r = run_downloader(f"{base}/mini_cabecalho_malformado.safetensors", out, MINI_MALFORMADO_SIZE, MINI_MALFORMADO_SHA256)
    registrar("C13 cabeçalho JSON malformado rejeitado", r.returncode != 0 and not out.exists(),
              f"rc={r.returncode}")

    # ---------------------------------------------------------------
    # Cenário 14: tensores com intervalos sobrepostos -> rejeita
    # ---------------------------------------------------------------
    out = WORK_DIR / "c14_sobreposicao.safetensors"
    limpar(out); limpar(Path(str(out) + ".part"))
    r = run_downloader(f"{base}/mini_sobreposicao.safetensors", out, MINI_SOBREPOSICAO_SIZE, MINI_SOBREPOSICAO_SHA256)
    registrar("C14 tensores sobrepostos rejeitado", r.returncode != 0 and not out.exists(),
              f"rc={r.returncode}")

    server.shutdown()

    print("\n" + "=" * 60)
    print(f"Testes aprovados: {sum(1 for _, ok, _ in resultados if ok)} / {len(resultados)}")
    for nome, ok, det in resultados:
        print(f"  [{'OK' if ok else 'FALHA'}] {nome} {det}")
    print("=" * 60)

    return 0 if all(ok for _, ok, _ in resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
