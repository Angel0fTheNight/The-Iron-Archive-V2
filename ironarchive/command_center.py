"""Command Center local — servidor HTTP leve para o THE IRON ARCHIVE 2.0.

Apenas biblioteca padrão do Python. Escuta exclusivamente em 127.0.0.1.
Nenhuma dependencia externa, nenhuma API paga, nenhum token no frontend.
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from ironarchive import core

HOST = "127.0.0.1"
PORT = int(os.environ.get("CC_PORT", "8765"))

WEBUI = Path(__file__).resolve().parent / "webui" / "index.html"

ROLE_LABELS = {
    "scout": "Scout — Pesquisa",
    "maester": "Maester — Roteiro e Lore",
    "artist": "Artist — Imagens",
    "editor": "Editor — Montagem",
    "inspector": "Inspector — QA",
    "engineer": "Engineer — Diagnóstico",
}
ROLE_KIND = {role: ("render" if role == "artist" else "review" if role == "inspector" else "prepare")
             for role in core.ROLES}

STATUS_LABELS = {
    "pending": "Pendente",
    "waiting_approval": "Aguardando aprovação",
    "prepared": "Preparado (manual)",
    "running": "Executando",
    "done": "Concluído",
    "failed": "Falhou",
    "rejected": "Rejeitado",
    "awaiting_integration": "Aguardando integração",
}


def _json(handler, code, obj):
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _text(handler, code, text, ctype="text/plain; charset=utf-8"):
    body = text.encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", ctype)
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _segments(path):
    return [s for s in path.strip("/").split("/") if s]


def _read_body(handler):
    """Lê o corpo JSON de uma requisição POST. Retorna dict (ou {} se vazio)."""
    length = int(handler.headers.get("Content-Length", 0) or 0)
    if length == 0:
        return {}
    raw = handler.rfile.read(length)
    try:
        return json.loads(raw.decode("utf-8")) if raw else {}
    except json.JSONDecodeError:
        return {}


class CommandHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return  # sem log de acesso no console do servidor

    def _job_id(self, segments):
        if len(segments) < 3 or segments[0] != "api" or segments[1] != "jobs":
            return None
        try:
            return int(segments[2])
        except ValueError:
            return None

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        params = parse_qs(parsed.query)
        segments = _segments(path)

        try:
            if path == "/":
                html = WEBUI.read_text(encoding="utf-8")
                _text(self, 200, html, "text/html; charset=utf-8")

            elif segments == ["api", "episodes"]:
                _json(self, 200, {"episodes": core.episodes()})

            elif segments[:2] == ["api", "jobs"] and len(segments) == 2:
                job_list = core.jobs()
                episode = params.get("episode", [None])[0]
                if episode is not None:
                    try:
                        job_list = [j for j in job_list if j["episode_id"] == int(episode)]
                    except ValueError:
                        pass
                _json(self, 200, {"jobs": job_list})

            elif segments[:2] == ["api", "jobs"] and len(segments) == 3:
                job_id = self._job_id(segments)
                job = core.get_job(job_id)
                if not job:
                    _json(self, 404, {"error": "job nao encontrado"})
                    return
                _json(self, 200, {
                    "job": job,
                    "events": core.get_events(job_id),
                    "output_available": bool(core.read_output(job_id)),
                    "output_meta": core.output_meta(job_id),
                }),

            elif segments[:2] == ["api", "jobs"] and len(segments) == 4 and segments[3] == "output":
                job_id = self._job_id(segments)
                content = core.read_output(job_id)
                if content is None:
                    _json(self, 404, {"error": "output nao encontrado"})
                    return
                _text(self, 200, content, "text/markdown; charset=utf-8")

            elif segments == ["api", "roles"]:
                _json(self, 200, {"roles": [
                    {"role": r, "label": ROLE_LABELS.get(r, r), "kind": ROLE_KIND[r]} for r in core.ROLES
                ]})

            elif segments == ["api", "logs"]:
                try:
                    limit = int(params.get("limit", ["100"])[0])
                except ValueError:
                    limit = 100
                events = []
                for j in core.jobs():
                    for e in core.get_events(j["id"]):
                        ev = dict(e)
                        ev["role"] = j["role"]
                        ev["episode_id"] = j["episode_id"]
                        events.append(ev)
                events.sort(key=lambda x: x["at"], reverse=True)
                _json(self, 200, {"events": events[:limit]})

            elif segments == ["api", "doctor"]:
                _json(self, 200, core.doctor())

            else:
                _json(self, 404, {"error": "endpoint nao encontrado"})

        except ValueError as exc:
            _json(self, 409, {"error": str(exc)})
        except Exception as exc:  # nao vazar stacktrace ao cliente
            _json(self, 500, {"error": f"erro interno: {exc}"})

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        segments = _segments(path)

        def decide(job_id, approve=None, prepare=False):
            try:
                if prepare:
                    core.mark_prepared(job_id)
                else:
                    core.change_approval(job_id, approve)
            except ValueError as exc:
                _json(self, 409, {"error": str(exc)})
                return None
            job = core.get_job(job_id)
            return {"id": job["id"], "status": job["status"], "ok": True}

        try:
            if segments == ["api", "run"]:
                result = core.run_one()
                if result is None:
                    _json(self, 200, {"status": "none_ready",
                                      "message": "Nenhuma etapa pronta. Verifique aprovações ou etapas anteriores."})
                else:
                    _json(self, 200, result)

            elif segments[:2] == ["api", "jobs"] and len(segments) == 4:
                job_id = self._job_id(segments)
                verb = segments[3]
                body = _read_body(self)
                if verb == "approve":
                    decided = decide(job_id, approve=True)
                elif verb == "reject":
                    decided = decide(job_id, approve=False)
                elif verb == "prepare":
                    decided = decide(job_id, prepare=True)
                elif verb == "retry":
                    confirmed = bool(body.get("confirm"))
                    try:
                        decided = core.retry_failed(job_id, confirm=confirmed)
                    except ValueError as exc:
                        _json(self, 409, {"error": str(exc)})
                        return None
                    job = core.get_job(job_id)
                    decided["status"] = job["status"]
                    return decided
                else:
                    _json(self, 404, {"error": "endpoint nao encontrado"})
                    return
                if decided is not None:
                    _json(self, 200, decided)

            else:
                _json(self, 404, {"error": "endpoint nao encontrado"})

        except ValueError as exc:
            _json(self, 409, {"error": str(exc)})
        except Exception as exc:
            _json(self, 500, {"error": f"erro interno: {exc}"})


def make_server(address, handler_class=CommandHandler):
    ThreadingHTTPServer.daemon_threads = True
    return ThreadingHTTPServer(address, handler_class)


def main():
    server = make_server((HOST, PORT))
    print(f"Command Center: http://{HOST}:{PORT} (somente local)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
