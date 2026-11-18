import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from ironarchive import core

ROLES = core.ROLES


def _make_env(t, execution_mode='manual'):
    agents = Path(t) / 'agents'
    agents.mkdir()
    for role in ROLES:
        (agents / f'{role}.md').write_text('Instruções de teste', encoding='utf-8')
    patches = [
        patch.object(core, 'DB', Path(t) / 'data' / 'retry.db'),
        patch.object(core, 'BASE', Path(t)),
        patch.object(core, 'settings', return_value={
            'execution_mode': execution_mode,
            'hermes': {'enabled': False},
            'safety': {'max_retry_attempts': 3},
        }),
    ]
    for p in patches:
        p.start()
    return patches


def _stop_patches(patches):
    for p in reversed(patches):
        p.stop()


def _set_status(db, job_id, status, attempts=0, error=None):
    db.execute(
        "UPDATE jobs SET status=?, attempts=?, error=?, updated_at=? WHERE id=?",
        (status, attempts, error, core.now(), job_id),
    )
    db.commit()


class TestRetry(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patches = _make_env(self.tmp.name)

    def tearDown(self):
        _stop_patches(self.patches)
        self.tmp.cleanup()

    def _status_and_events(self, job_id):
        with core.connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            events = db.execute(
                "SELECT * FROM events WHERE job_id=? ORDER BY id", (job_id,)
            ).fetchall()
        return dict(row) if row else None, [dict(e) for e in events]

    # 1. Sucesso: job failed -> pending, evento de auditoria, attempts preservados
    def test_retry_success_marks_pending_and_audits(self):
        core.create_episode('Episodio Retry', 'Objetivo de teste')
        # job 1 = scout, inicialmente pending. Força failed com attempts=2 e erro.
        with core.connect() as db:
            _set_status(db, 1, 'failed', attempts=2,
                        error='Hermes saiu com código 1: session_id: local-xxx')

        res = core.retry_failed(1, confirm=True)
        self.assertEqual(res['status'], 'pending')
        self.assertEqual(res['previous_status'], 'failed')
        self.assertEqual(res['previous_error'],
                         'Hermes saiu com código 1: session_id: local-xxx')
        self.assertEqual(res['attempts'], 2)  # nao zerado
        self.assertEqual(res['max_attempts'], 3)

        job, events = self._status_and_events(1)
        self.assertEqual(job['status'], 'pending')
        self.assertEqual(job['attempts'], 2)  # nao zerado no banco
        self.assertIsNone(job['error'])  # erro limpo no retry
        self.assertGreaterEqual(len(events), 1)
        retry_events = [e for e in events if 'retry' in e['event']]
        self.assertEqual(len(retry_events), 1)
        self.assertIn('failed->pending', retry_events[0]['event'])
        self.assertIn('erro anterior:', retry_events[0]['event'])

    # 2. Ausência de confirmação -> ValueError
    def test_retry_without_confirm_rejected(self):
        core.create_episode('Episodio Retry', 'Objetivo de teste')
        with core.connect() as db:
            _set_status(db, 1, 'failed', attempts=1)

        with self.assertRaises(ValueError) as ctx:
            core.retry_failed(1, confirm=False)
        self.assertIn('Confirmação explícita', str(ctx.exception))

        # banco inalterado
        job, _ = self._status_and_events(1)
        self.assertEqual(job['status'], 'failed')

    # 3. Estado incompatível (não failed) -> ValueError
    def test_retry_only_failed(self):
        core.create_episode('Episodio Retry', 'Objetivo de teste')
        for status in ('pending', 'waiting_approval', 'prepared', 'running',
                       'done', 'rejected', 'awaiting_integration'):
            with core.connect() as db:
                _set_status(db, 1, status, attempts=0)
            with self.assertRaises(ValueError) as ctx:
                core.retry_failed(1, confirm=True)
            self.assertIn('Somente jobs falhados', str(ctx.exception))

    # 4. Limite de tentativas: attempts >= max -> ValueError
    def test_retry_max_attempts_rejected(self):
        core.create_episode('Episodio Retry', 'Objetivo de teste')
        with core.connect() as db:
            _set_status(db, 1, 'failed', attempts=3)  # igual a max=3

        with self.assertRaises(ValueError) as ctx:
            core.retry_failed(1, confirm=True)
        self.assertIn('Limite de tentativas atingido', str(ctx.exception))
        self.assertIn('3/3', str(ctx.exception))

        # banco inalterado
        job, _ = self._status_and_events(1)
        self.assertEqual(job['status'], 'failed')
        self.assertEqual(job['attempts'], 3)

    # 5. Dependências: predecessor não liberado -> ValueError
    def test_retry_blocked_by_predecessor(self):
        core.create_episode('Episodio Retry', 'Objetivo de teste')
        # job 1 (scout) failed, job 2 (maester) pending -> tentar retry no job 2?
        # nao: job 2 nao está failed. Coloca job 1 failed e tenta retry no job 3 (artist)
        # com predecessor job 2 (maester) ainda pending -> bloqueado.
        with core.connect() as db:
            _set_status(db, 1, 'failed', attempts=1)
            _set_status(db, 2, 'pending', attempts=0)
            _set_status(db, 3, 'failed', attempts=1)  # artist, kind render

        with self.assertRaises(ValueError) as ctx:
            core.retry_failed(3, confirm=True)
        self.assertIn('Dependências do episódio não liberadas', str(ctx.exception))

        # banco inalterado
        job, _ = self._status_and_events(3)
        self.assertEqual(job['status'], 'failed')

    # 6. Concorrência: segundo retry após status já mudou -> ValueError
    def test_retry_concurrent_duplicate_rejected(self):
        core.create_episode('Episodio Retry', 'Objetivo de teste')
        with core.connect() as db:
            _set_status(db, 1, 'failed', attempts=1)

        # Primeiro retry sucesso
        res1 = core.retry_failed(1, confirm=True)
        self.assertEqual(res1['status'], 'pending')

        # Segundo retry: job nao está mais em failed -> rejeitado (estado incompatível)
        with self.assertRaises(ValueError) as ctx:
            core.retry_failed(1, confirm=True)
        self.assertIn('Somente jobs falhados', str(ctx.exception))

        job, events = self._status_and_events(1)
        self.assertEqual(job['status'], 'pending')
        retry_events = [e for e in events if 'retry' in e['event']]
        self.assertEqual(len(retry_events), 1)  # apenas um evento de retry


if __name__ == '__main__':
    unittest.main()
