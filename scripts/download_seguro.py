#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
download_seguro.py - The Iron Archive V2

Download seguro de checkpoints .safetensors usando apenas a biblioteca padrão
do Python. Projetado para baixar apenas após aprovação explícita e com validações
rígidas contra corrupção, retomada inadequada e esgotamento de disco.

Neste arquivo NÃO há download automático: ele deve ser invocado via linha de
comando com URL, tamanho oficial e SHA-256 conhecidos.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

CHUNK_SIZE = 65536
MAX_PART_DEFAULT = 8 * 1024 * 1024 * 1024       # 8 GiB temporário
MAX_ATTEMPTS_DEFAULT = 3
TIMEOUT_DEFAULT = 300                            # segundos
MIN_FREE_DISK_DEFAULT = 50 * 1024 * 1024 * 1024 # 50 GB livres em D:
MAX_TOTAL_DURATION_DEFAULT = 4 * 60 * 60  # 4 horas em segundos

CONTENT_RANGE_FULL_RE = re.compile(r"^bytes\s+(\d+)-(\d+)/(\d+)$", re.IGNORECASE)
CONTENT_RANGE_STAR_RE = re.compile(r"^bytes\s+(\d+)-(\d+)/\*$", re.IGNORECASE)


def utc_now():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def setup_logging(log_dir: Path):
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = utc_now().replace(":", "-").replace(" ", "_")
    log_file = log_dir / f"download_seguro_{stamp}.log"

    def log(msg):
        line = f"[{utc_now()}] {msg}"
        print(line, flush=True)
        with open(log_file, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    return log, log_file


def free_space_bytes(path: Path) -> int:
    try:
        return shutil.disk_usage(str(path)).free
    except Exception:
        return 0


def acquire_lock(lock_path: Path):
    """Tenta criar um arquivo de travamento exclusivo (.lock). Retorna fd ou None."""
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
        return fd
    except FileExistsError:
        return None
    except Exception:
        return None


def release_lock(fd, lock_path: Path):
    try:
        os.close(fd)
    except Exception:
        pass
    try:
        os.remove(str(lock_path))
    except Exception:
        pass


def compute_sha256(path: Path, log) -> tuple:
    h = hashlib.sha256()
    total = 0
    with open(path, "rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            h.update(chunk)
            total += len(chunk)
    return h.hexdigest(), total


def validate_safetensors_structure(path: Path, expected_size: int, log) -> tuple:
    """
    Valida a estrutura interna de um .safetensors conforme a especificação oficial:

      - cabeçalho de 8 bytes (little-endian u64) com tamanho do JSON
      - JSON parseável
      - chave especial "__metadata__": metadados embutidos no cabeçalho, SEM data_offsets
      - demais chaves são tensores com "data_offsets" relativos ao início da
        região de dados (após os 8 bytes do prefixo + header_len bytes do JSON)
      - tamanho_total = 8 + header_len + tamanho_da_região_de_dados
      - intervalos de tensores não se sobrepõem e respeitam os limites da região de dados
    """
    try:
        size = os.path.getsize(path)
        if size != expected_size:
            return False, f"tamanho {size} != esperado {expected_size}"
        with open(path, "rb") as f:
            header_len_bytes = f.read(8)
            if len(header_len_bytes) < 8:
                return False, "cabeçalho truncado (<8 bytes)"
            header_len = int.from_bytes(header_len_bytes, "little")
            if header_len <= 0 or header_len > size - 8:
                return False, f"tamanho do cabeçalho inválido: {header_len}"
            header_bytes = f.read(header_len)
            if len(header_bytes) < header_len:
                return False, "corpo do cabeçalho truncado"
            try:
                meta = json.loads(header_bytes.decode("utf-8"))
            except Exception as e:
                return False, f"JSON do cabeçalho inválido: {e}"

            if not isinstance(meta, dict):
                return False, "cabeçalho não é um objeto JSON"

            # Região de dados começa após o prefixo (8) + cabeçalho JSON (header_len)
            dados_inicio = 8 + header_len

            max_offset_relativo = 0
            intervalos = []  # (start, end, nome) para detecção de sobreposição

            for nome, info in meta.items():
                # --- Chave especial __metadata__: metadados embutidos, não é tensor ---
                if nome == "__metadata__":
                    if not isinstance(info, dict):
                        return False, "chave '__metadata__' não é um objeto JSON"
                    # __metadata__ NÃO deve ter data_offsets; se tiver, deve ser ausente/None
                    if "data_offsets" in info and info.get("data_offsets") is not None:
                        return False, "chave '__metadata__' não deve conter data_offsets"
                    continue

                # --- Tensor válido: deve ter data_offsets ---
                offs = info.get("data_offsets")
                if not isinstance(offs, list) or len(offs) != 2:
                    return False, f"tensor '{nome}': data_offsets inválido ou ausente"
                start, end = offs
                if not isinstance(start, int) or not isinstance(end, int):
                    return False, f"tensor '{nome}': offsets não inteiros"
                if start < 0:
                    return False, f"tensor '{nome}': offset inicial negativo ({start})"
                if end <= start:
                    return False, f"tensor '{nome}': offset final ({end}) <= inicial ({start})"
                if end > (size - dados_inicio):
                    return False, f"tensor '{nome}': offset final {end} excede região de dados ({size - dados_inicio})"

                intervalos.append((start, end, nome))
                if end > max_offset_relativo:
                    max_offset_relativo = end

            # Verificar sobreposição entre intervalos de tensores
            intervalos.sort()
            for i in range(1, len(intervalos)):
                prev_end = intervalos[i - 1][1]
                curr_start = intervalos[i][0]
                if curr_start < prev_end:
                    return False, f"tensor '{intervalos[i][2]}': intervalo se sobrepõe ao de '{intervalos[i-1][2]}'"

            # Tamanho total = prefixo + cabeçalho + região de dados
            tamanho_total = dados_inicio + max_offset_relativo
            if tamanho_total != size:
                return False, f"tamanho calculado ({tamanho_total}) != tamanho do arquivo ({size})"

        return True, "estrutura safetensors válida"
    except Exception as e:
        return False, f"erro na validação de estrutura: {e}"


def parse_content_range(content_range: str, requested_start: int, size_expected: int):
    """
    Valida o cabeçalho Content-Range de uma resposta 206.
    Retorna (ok: bool, motivo: str).
    Aceita 'bytes <start>-<end>/<total>' e 'bytes <start>-<end>/*'.
    """
    if not content_range:
        return False, "Content-Range ausente"
    m = CONTENT_RANGE_FULL_RE.match(content_range.strip()) or CONTENT_RANGE_STAR_RE.match(content_range.strip())
    if not m:
        return False, f"formato Content-Range inválido: {content_range}"
    start, end, total = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if start != requested_start:
        return False, f"início {start} != solicitado {requested_start}"
    if end < start:
        return False, f"fim {end} < início {start}"
    if total != size_expected:
        return False, f"total {total} != oficial {size_expected}"
    return True, "Content-Range válido"


def http_open(url, range_header=None, timeout=TIMEOUT_DEFAULT):
    """
    Abre a URL e retorna (status, headers, stream).
    Em caso de HTTPError, retorna (code, headers, stream_do_erro).
    """
    req = urllib.request.Request(url, headers={"User-Agent": "TheIronArchive-V2/1.0"})
    if range_header:
        req.add_header("Range", range_header)
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.status, resp.headers, resp
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e
    except Exception:
        raise


def download_seguro(
    url: str,
    out_path: str,
    size_expected: int,
    sha256_expected: str,
    max_part: int = MAX_PART_DEFAULT,
    max_attempts: int = MAX_ATTEMPTS_DEFAULT,
    timeout: int = TIMEOUT_DEFAULT,
    min_free_disk: int = MIN_FREE_DISK_DEFAULT,
    max_total_duration: int = MAX_TOTAL_DURATION_DEFAULT,
    log=None,
):
    out_path = Path(out_path)
    part_path = out_path.parent / (out_path.name + ".part")
    lock_path = out_path.parent / (out_path.name + ".lock")
    log_dir = out_path.parent / "logs"
    if log is None:
        log, _ = setup_logging(log_dir)

    # Limite de duração total (4h padrão), medido com time.monotonic(),
    # independente do timeout de soquete (300s) e incluindo todas as tentativas.
    # O timeout de soquete pode atrasar a interrupção em até 300 segundos,
    # pois só é verificado em operações de rede bloqueantes.
    inicio_monotonic = time.monotonic()

    def duracao_excedida() -> bool:
        return (time.monotonic() - inicio_monotonic) > max_total_duration

    # Req. 10: nunca sobrescrever checkpoint existente
    if out_path.exists():
        log(f"ABORTO: checkpoint final já existe: {out_path}")
        return False, "checkpoint_final_existente"

    # Req. 6: espaço livre antes de iniciar
    free = free_space_bytes(out_path.parent)
    log(f"Espaço livre em {out_path.parent}: {free} bytes (mínimo {min_free_disk})")
    if free < min_free_disk:
        log(f"ABORTO: espaço livre insuficiente ({free} < {min_free_disk})")
        return False, "espaco_insuficiente"

    # Req. 7: trava exclusiva por arquivo
    fd = acquire_lock(lock_path)
    if fd is None:
        log(f"ABORTO: travada ocupada — outro download de {out_path.name} em andamento")
        return False, "trava_ocupada"

    try:
        # Inspeciona .part pré-existente (Req. 11: não apagar sem autorização)
        tamanho_base = 0
        if part_path.exists():
            tamanho_base = part_path.stat().st_size
            log(f".part existente encontrado: {tamanho_base} bytes")
            if tamanho_base > size_expected:
                log(f"ABORTO: .part ({tamanho_base}) excede tamanho oficial ({size_expected})")
                return False, "part_excede_oficial"
            if tamanho_base == size_expected:
                sha_atual, _ = compute_sha256(part_path, log)
                ok_struc, msg_struc = validate_safetensors_structure(part_path, size_expected, log)
                if sha_atual == sha256_expected and ok_struc:
                    os.replace(part_path, out_path)
                    log(f"SUCESSO: .part válido renomeado para {out_path}")
                    return True, "sucesso"
                else:
                    log(f"ABORTO: .part com tamanho oficial mas inválido (sha={sha_atual}, struc={msg_struc})")
                    return False, "part_invalido"

        tentativa = 0
        tamanho_atual = tamanho_base

        while tentativa < max_attempts:
            tentativa += 1

            if duracao_excedida():
                log("ABORTO: duração total excedeu o limite de 4 horas")
                return False, "duracao_total_excedida"

            # Req. 6: espaço livre durante a operação
            if free_space_bytes(out_path.parent) < min_free_disk:
                log("ABORTO: espaço livre caiu abaixo do mínimo durante a operação")
                return False, "espaco_insuficiente_durante"

            if tamanho_atual > 0:
                range_header = f"bytes={tamanho_atual}-"
            else:
                range_header = None

            log(f"Tentativa {tentativa}/{max_attempts}: GET {url} (Range: {range_header})")
            try:
                status, headers, stream = http_open(url, range_header, timeout)
            except Exception as e:
                log(f"Tentativa {tentativa}: erro na requisição: {e}")
                if tentativa >= max_attempts:
                    return False, "erro_requisicao"
                time.sleep(2)
                continue

            content_range = headers.get("Content-Range") or headers.get("content-range")

            # Req. 3 e 4: decidir modo de gravação com base no status
            if status == 200:
                if tamanho_atual > 0:
                    log(f"Tentativa {tentativa}: servidor respondeu 200 na retomada — NÃO acrescentando ao .part existente")
                    return False, "servidor_200_sem_retomada"
                modo = "wb"
            elif status == 206:
                ok_cr, msg_cr = parse_content_range(content_range, tamanho_atual, size_expected)
                if not ok_cr:
                    log(f"Tentativa {tentativa}: Content-Range inválido: {content_range} ({msg_cr})")
                    if tentativa >= max_attempts:
                        return False, "content_range_invalido"
                    time.sleep(2)
                    continue
                modo = "ab" if tamanho_atual > 0 else "wb"
            else:
                log(f"Tentativa {tentativa}: status HTTP inesperado {status}")
                if tentativa >= max_attempts:
                    return False, f"status_http_{status}"
                time.sleep(2)
                continue

            # Req. 5: gravação bloco a bloco com verificação de tamanho
            gravados = 0
            try:
                with open(part_path, modo) as f:
                    while True:
                        chunk = stream.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        total_projetado = tamanho_atual + gravados + len(chunk)
                        if total_projetado > size_expected:
                            log(f"ABORTO: gravação excederia tamanho oficial ({total_projetado} > {size_expected})")
                            return False, "excede_tamanho_oficial"
                        if total_projetado > max_part:
                            log("ABORTO: .part excederia limite temporário de 8 GiB")
                            return False, "excede_max_part"
                        f.write(chunk)
                        gravados += len(chunk)
                        if gravados % (CHUNK_SIZE * 16) == 0:
                            if free_space_bytes(out_path.parent) < min_free_disk:
                                log("ABORTO: espaço livre insuficiente durante gravação")
                                return False, "espaco_insuficiente_durante_gravacao"
                            if duracao_excedida():
                                log("ABORTO: duração total excedeu o limite durante gravação")
                                return False, "duracao_total_excedida"
            except Exception as e:
                log(f"Erro durante gravação: {e}")
                return False, "erro_gravacao"

            tamanho_atual = tamanho_base + gravados
            log(f"Tentativa {tentativa}: {gravados} bytes gravados. Total .part: {tamanho_atual} / {size_expected}")

            if tamanho_atual < size_expected:
                tamanho_base = tamanho_atual  # atualiza base para próxima tentativa
                log(f"DOWNLOAD INCOMPLETO: {tamanho_atual} / {size_expected}")
                if tentativa >= max_attempts:
                    return False, "download_incompleto"
                continue

            break

        # Req. 9: validações finais antes de renomear
        if tamanho_atual != size_expected:
            log(f"FALHA: tamanho final {tamanho_atual} != esperado {size_expected}")
            return False, "tamanho_final_errado"

        sha_atual, _ = compute_sha256(part_path, log)
        if sha_atual != sha256_expected:
            log(f"FALHA: SHA-256 {sha_atual} != esperado {sha256_expected}")
            return False, "hash_incorreto"

        ok_struc, msg_struc = validate_safetensors_structure(part_path, size_expected, log)
        if not ok_struc:
            log(f"FALHA: estrutura safetensors inválida: {msg_struc}")
            return False, "estrutura_invalida"

        # Renomeia somente após validação completa
        os.replace(part_path, out_path)
        log(f"SUCESSO: {out_path} criado e validado.")
        return True, "sucesso"

    finally:
        release_lock(fd, lock_path)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Download seguro de checkpoint .safetensors (The Iron Archive V2)")
    parser.add_argument("--url", required=True, help="URL do arquivo a baixar")
    parser.add_argument("--out", required=True, help="Caminho final do .safetensors")
    parser.add_argument("--size", type=int, required=True, help="Tamanho oficial em bytes")
    parser.add_argument("--sha256", required=True, help="SHA-256 oficial")
    parser.add_argument("--max-part", type=int, default=MAX_PART_DEFAULT, help="Limite do .part (bytes)")
    parser.add_argument("--max-attempts", type=int, default=MAX_ATTEMPTS_DEFAULT, help="Tentativas máximas")
    parser.add_argument("--timeout", type=int, default=TIMEOUT_DEFAULT, help="Timeout da requisição (s)")
    parser.add_argument("--min-free-disk", type=int, default=MIN_FREE_DISK_DEFAULT, help="Espaço mínimo livre em D: (bytes)")
    parser.add_argument("--max-total-duration", type=int, default=MAX_TOTAL_DURATION_DEFAULT, help="Limite de duração total em segundos (padrão 4 horas)")
    args = parser.parse_args(argv)

    ok, motivo = download_seguro(
        url=args.url,
        out_path=args.out,
        size_expected=args.size,
        sha256_expected=args.sha256,
        max_part=args.max_part,
        max_attempts=args.max_attempts,
        timeout=args.timeout,
        max_total_duration=args.max_total_duration,
        min_free_disk=args.min_free_disk,
    )
    if ok:
        print(f"RESULTADO: SUCESSO ({motivo})")
        return 0
    else:
        print(f"RESULTADO: FALHA ({motivo})")
        return 1


if __name__ == "__main__":
    sys.exit(main())
