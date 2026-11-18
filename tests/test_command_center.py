import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

from ironarchive import core
from ironarchive.command_center import make_server

ROLES = core.ROLES


def _make_env(t):
    agents = Path(t) / 'agents'
    agents.mkdir()
    for role in ROLES:
        (agents / f'{role}.md').write_text('Instruções de teste', encoding='utf-8')
    patches = [
        patch.object(core, 'DB', Path(t) / 'data' / 'cc.db'),
        patch.object(core, 'BASE', Path(t)),
        patch.object(core, 'settings', return_value={'execution_mode': 'manual', 'hermes': {'enabled': False}}),
    ]
    for p in patches:
        p.start()
    return patches


def _stop_patches(patches):
    for p in reversed(patches):
        p.stop()


def _start_server():
    server = make_server(('127.0.0.1', 0))
    _host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port


def _req(method, path, port, body=None):
    url = f'http://127.0.0.1:{port}{path}'
    data = json.dumps(body).encode('utf-8') if body is not None else None
    request = urllib.request.Request(url, data=data, method=method,
                                     headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            text = response.read().decode('utf-8')
            return response.status, _decode(text, response.headers.get('Content-Type', ''))
    except urllib.error.HTTPError as error:
        text = error.read().decode('utf-8')
        return error.code, _decode(text, error.headers.get('Content-Type', ''))


def _decode(text, content_type):
    if 'application/json' in content_type:
        return json.loads(text)
    return text


class TestCommandCenter(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patches = _make_env(self.tmp.name)
        self.server, self.port = _start_server()
        self.episode = core.create_episode('Episodio Teste', 'Objetivo de teste')

    def tearDown(self):
        try:
            self.server.shutdown()
        except Exception:
            pass
        _stop_patches(self.patches)
        self.tmp.cleanup()

    def test_bind_loopback_only(self):
        self.assertEqual(self.server.server_address[0], '127.0.0.1')

    def test_episodes_and_jobs(self):
        code, body = _req('GET', '/api/episodes', self.port)
        self.assertEqual(code, 200)
        self.assertTrue(any(e['slug'] == self.episode[1] for e in body["episodes"]))

        code, body = _req('GET', '/api/jobs', self.port)
        self.assertEqual(code, 200)
        self.assertEqual(len(body["jobs"]), 6)
        self.assertEqual({j['role'] for j in body["jobs"]}, set(ROLES))
        artist = next(j for j in body["jobs"] if j['role'] == 'artist')
        self.assertEqual(artist['status'], 'waiting_approval')

        code, body = _req('GET', '/api/roles', self.port)
        self.assertEqual(code, 200)
        self.assertEqual(len(body["roles"]), 6)

        code, body = _req('GET', '/api/doctor', self.port)
        self.assertEqual(code, 200)
        self.assertIn('python', body)

    def test_approve_and_reject_only_waiting_approval(self):
        code, _payload = _req('GET', '/api/jobs', self.port)
        jobs = _payload["jobs"]
        scout = next(j for j in jobs if j['role'] == 'scout')
        artist = next(j for j in jobs if j['role'] == 'artist')
        aid = artist['id']

        # falha: scout nao esta waiting_approval
        code, _ = _req('POST', f'/api/jobs/{scout["id"]}/approve', self.port)
        self.assertEqual(code, 409)

        code, body = _req('POST', f'/api/jobs/{aid}/approve', self.port)
        self.assertEqual(code, 200)
        self.assertEqual(body['status'], 'pending')

        # ja nao aguarda aprovacao: nem nova aprovacao nem rejeicao se aplicam
        code, _ = _req('POST', f'/api/jobs/{aid}/approve', self.port)
        self.assertEqual(code, 409)
        code, _ = _req('POST', f'/api/jobs/{aid}/reject', self.port)
        self.assertEqual(code, 409)

        # rejeicao direta so faz sentido em outro job waiting_approval (novo episodio)
        eid2, _slug2 = core.create_episode('Segundo Episodio', 'Outro objetivo')
        code, _payload = _req('GET', '/api/jobs', self.port)
        jobs2 = _payload["jobs"]
        rej = next(j for j in jobs2 if j['role'] == 'artist' and j['episode_id'] == eid2)
        code, body = _req('POST', f'/api/jobs/{rej["id"]}/reject', self.port)
        self.assertEqual(code, 200)
        self.assertEqual(body['status'], 'rejected')
        code, _ = _req('POST', f'/api/jobs/{rej["id"]}/approve', self.port)
        self.assertEqual(code, 409)

        code, body = _req('GET', f'/api/jobs/{rej["id"]}', self.port)
        self.assertEqual(code, 200)
        self.assertEqual(body['job']['status'], 'rejected')
        self.assertGreaterEqual(len(body.get('events', [])), 1)

        code, logs = _req('GET', '/api/logs', self.port)
        self.assertEqual(code, 200)
        events = logs["events"] if isinstance(logs, dict) else logs
        self.assertTrue(any(l['job_id'] == aid for l in events))
        self.assertTrue(any(l['job_id'] == rej['id'] for l in events))

    def test_prepare_only_pending(self):
        code, _payload = _req('GET', '/api/jobs', self.port)
        jobs = _payload["jobs"]
        maester = next(j for j in jobs if j['role'] == 'maester')
        artist = next(j for j in jobs if j['role'] == 'artist')

        code, body = _req('POST', f'/api/jobs/{maester["id"]}/prepare', self.port)
        self.assertEqual(code, 200)
        self.assertEqual(body['status'], 'prepared')

        code, _ = _req('POST', f'/api/jobs/{maester["id"]}/prepare', self.port)
        self.assertEqual(code, 409)

        code, _ = _req('POST', f'/api/jobs/{artist["id"]}/prepare', self.port)
        self.assertEqual(code, 409)

    def test_run_executes_next_ready_job(self):
        code, _payload = _req('GET', '/api/jobs', self.port)
        jobs = _payload["jobs"]
        ids = {j['role']: j['id'] for j in jobs}
        with core.connect() as db:
            db.execute("UPDATE jobs SET status='done' WHERE id=?", (ids['scout'],))
            db.execute("UPDATE jobs SET status='prepared' WHERE id=?", (ids['maester'],))
            db.execute("UPDATE jobs SET status='done' WHERE id=?", (ids['artist'],))
            db.commit()

        code, body = _req('POST', '/api/run', self.port)
        self.assertEqual(code, 200)
        self.assertEqual(body['role'], 'editor')
        self.assertEqual(body['status'], 'awaiting_integration')

        code, body = _req('POST', '/api/run', self.port)
        self.assertEqual(code, 200)
        self.assertEqual(body['status'], 'none_ready')

        code, body = _req('GET', f"/api/jobs/{ids['editor']}", self.port)
        self.assertEqual(body['job']['status'], 'awaiting_integration')

    def test_output_detail_and_missing(self):
        code, _payload = _req('GET', '/api/jobs', self.port)
        jobs = _payload["jobs"]
        scout_id = next(j['id'] for j in jobs if j['role'] == 'scout')

        code, body = _req('GET', f'/api/jobs/{scout_id}', self.port)
        self.assertEqual(code, 200)
        self.assertEqual(body['job']['role'], 'scout')
        self.assertIn('title', body['job'])

        code, _ = _req('GET', f'/api/jobs/{scout_id}/output', self.port)
        self.assertEqual(code, 404)

        code, _ = _req('GET', '/api/jobs/999999', self.port)
        self.assertEqual(code, 404)

        with core.connect() as db:
            row = db.execute('SELECT * FROM jobs WHERE id=?', (scout_id,)).fetchone()
        path = core.output_path(core.get_job(scout_id))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('## Evidências\n\nConteúdo de teste do scout.', encoding='utf-8')

        code, body = _req('GET', f'/api/jobs/{scout_id}/output', self.port)
        self.assertEqual(code, 200)
        self.assertIn('Evidências', body)


if __name__ == '__main__':
    unittest.main()
