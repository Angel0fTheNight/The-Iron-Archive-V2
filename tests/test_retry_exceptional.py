import tempfile
import threading
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

from ironarchive import core

ROLES = core.ROLES


def _proc(returncode=0, stdout='', stderr=''):
    m = MagicMock()
    m.returncode = returncode
    m.stdout = stdout
    m.stderr = stderr
    return m


def _make_env(t, execution_mode='hermes'):
    agents = Path(t) / 'agents'
    agents.mkdir()
    for role in ROLES:
        (agents / f'{role}.md').write_text('Instruções de teste', encoding='utf-8')
    patches = [
        patch.object(core, 'DB', Path(t) / 'data' / 'retry_exc.db'),
        patch.object(core, 'BASE', Path(t)),
        patch.object(core, 'settings', return_value={
            'execution_mode': execution_mode,
            'hermes': {'enabled': True, 'command': ['hermes'], 'timeout_seconds': 120,
                       'args_template': ['chat', '--query-file', '{prompt_file}', '--oneshot',
                                         '--quiet', '--format', 'text', '--max-turns', '6',
                                         '--run-budget', '150', '--source', 'tool']},
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


class TestRetryExceptional(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patches = _make_env(self.tmp.name)

    def tearDown(self):
        _stop_patches(self.patches)
        self.tmp.cleanup()

    def _status(self, job_id):
        with core.connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return dict(row) if row else None

    def _events(self, job_id):
        with core.connect() as db:
            rows = db.execute(
                "SELECT * FROM events WHERE job_id=? ORDER BY id", (job_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    # 1. Autorização: sem confirm -> rejeitado, nada muda
    def test_sem_confirm_rejeitado(self):
        core.create_episode('E1', 'Objetivo')
        with core.connect() as db:
            _set_status(db, 1, 'failed', attempts=3, error='x')
        with self.assertRaises(ValueError) as ctx:
            core.retry_exceptional(1, confirm=False, justificativa='justificativa qualquer')
        self.assertIn('Confirmação explícita', str(ctx.exception))
        job = self._status(1)
        self.assertEqual(job['status'], 'failed')
        self.assertEqual(job['attempts'], 3)

    # 2. Autorização: justificativa vazia -> rejeitado, nada muda
    def test_sem_justificativa_rejeitado(self):
        core.create_episode('E1', 'Objetivo')
        with core.connect() as db:
            _set_status(db, 1, 'failed', attempts=3, error='x')
        with self.assertRaises(ValueError) as ctx:
            core.retry_exceptional(1, confirm=True, justificativa='')
        self.assertIn('Justificativa não vazia', str(ctx.exception))
        job = self._status(1)
        self.assertEqual(job['status'], 'failed')

    # 3. Escopo: apenas job 1 (scout, episódio 1)
    def test_escopo_apenas_job1_scout(self):
        core.create_episode('E1', 'Objetivo')
        core.create_episode('E2', 'Outro')
        with core.connect() as db:
            _set_status(db, 1, 'failed', attempts=3, error='x')
            _set_status(db, 7, 'failed', attempts=3, error='x')  # scout do outro episódio
            _set_status(db, 2, 'failed', attempts=3, error='x')  # maester do episódio 1
        # job 7 (outro episódio) não é elegível
        with self.assertRaises(ValueError) as ctx:
            core.retry_exceptional(7, confirm=True, justificativa='justificativa')
        self.assertIn('restrita ao job #1', str(ctx.exception))
        # job 2 (maester) não é elegível
        with self.assertRaises(ValueError) as ctx:
            core.retry_exceptional(2, confirm=True, justificativa='justificativa')
        self.assertIn('restrita ao job #1', str(ctx.exception))
        # nada mudou
        for jid in (1, 2, 7):
            self.assertEqual(self._status(jid)['status'], 'failed')

    # 4. Auditoria: evento com justificativa, attempts anteriores, transição, excepcional
    def test_auditoria_registra_justificativa_e_attempts(self):
        core.create_episode('E1', 'Objetivo')
        with core.connect() as db:
            _set_status(db, 1, 'failed', attempts=3, error='erro antigo')
        res = core.retry_exceptional(
            1,
            confirm=True,
            justificativa='Falha persistente do placeholder após correção de contexto.',
            autorizador='operador',
        )
        self.assertEqual(res['status'], 'pending')
        self.assertEqual(res['attempts'], 3)  # preservado
        self.assertTrue(res['exceptional'])
        self.assertEqual(res['justificativa'], 'Falha persistente do placeholder após correção de contexto.')
        job = self._status(1)
        self.assertEqual(job['status'], 'pending')
        self.assertEqual(job['attempts'], 3)
        evts = self._events(1)
        exc_events = [e for e in evts if 'retry_exceptional' in e['event']]
        self.assertEqual(len(exc_events), 1)
        ev = exc_events[0]['event']
        self.assertIn('failed->pending', ev)
        self.assertIn('attempts=3/3', ev)
        self.assertIn('justificativa=', ev)
        self.assertIn('Falha persistente do placeholder', ev)

    # 5. Atomicidade: job não está mais em failed -> nenhuma alteração parcial
    def test_nao_estado_falho_nao_altera(self):
        core.create_episode('E1', 'Objetivo')
        with core.connect() as db:
            _set_status(db, 1, 'pending', attempts=3)
        with self.assertRaises(ValueError) as ctx:
            core.retry_exceptional(1, confirm=True, justificativa='justificativa')
        self.assertIn('Somente jobs falhados', str(ctx.exception))
        job = self._status(1)
        self.assertEqual(job['status'], 'pending')
        self.assertEqual(job['attempts'], 3)

    # 6. Concorrência: apenas uma recuperação tem sucesso; a outra falha por estado
    def test_concorrencia_apenas_uma_recuperacao(self):
        import threading  # noqa: F401  (importado localmente para o teste)
        core.create_episode('E1', 'Objetivo')
        with core.connect() as db:
            _set_status(db, 1, 'failed', attempts=3, error='x')
        resultados = []

        def tentar(tag):
            try:
                r = core.retry_exceptional(1, confirm=True, justificativa='concorrente ' + tag)
                resultados.append(('ok', tag, r['status']))
            except ValueError as e:
                resultados.append(('erro', tag, str(e)))

        t1 = threading.Thread(target=tentar, args=('A',))
        t2 = threading.Thread(target=tentar, args=('B',))
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        ok = [r for r in resultados if r[0] == 'ok']
        erros = [r for r in resultados if r[0] == 'erro']
        self.assertEqual(len(ok), 1, 'apenas uma recuperação deve ter sucesso')
        self.assertEqual(len(erros), 1, 'a outra deve falhar por concorrência/estado')
        job = self._status(1)
        self.assertEqual(job['status'], 'pending')
        self.assertEqual(job['attempts'], 3)

    # 7. attempts preservado em 3 na recuperação; run_one incrementa para 4 (tentativa excepcional)
    def test_attempts_preservado_e_incrementa_na_execucao(self):
        core.create_episode('E1', 'Objetivo')
        with core.connect() as db:
            _set_status(db, 1, 'failed', attempts=3, error='x')
        res = core.retry_exceptional(1, confirm=True, justificativa='justificativa')
        self.assertEqual(res['attempts'], 3)
        job = self._status(1)
        self.assertEqual(job['status'], 'pending')
        self.assertEqual(job['attempts'], 3)

        # run_one executa o scout (hermes mockado, saída válida) -> attempts 4, done
        valido = (
            '## Evidências\nhttps://exemplo.com/fonte\n## Plano\nplano\n'
            '## Pendências\npendente\n## Próxima ação\nacao\n' + 'z' * 300
        )
        with patch('subprocess.run', return_value=_proc(returncode=0, stdout=valido, stderr='')):
            out = core.run_one()
        self.assertEqual(out['role'], 'scout')
        self.assertIn('output', out)
        job = self._status(1)
        self.assertEqual(job['status'], 'done')
        self.assertEqual(job['attempts'], 4)  # incrementado por run_one (tentativa excepcional)

    # 8. Limite normal preservado: retry_failed ainda bloqueia em 3/3 (separação dos caminhos)
    def test_retry_normal_nao_afetado(self):
        core.create_episode('E1', 'Objetivo')
        with core.connect() as db:
            _set_status(db, 1, 'failed', attempts=3, error='x')
        with self.assertRaises(ValueError) as ctx:
            core.retry_failed(1, confirm=True)
        self.assertIn('Limite de tentativas atingido', str(ctx.exception))
        job = self._status(1)
        self.assertEqual(job['status'], 'failed')
        self.assertEqual(job['attempts'], 3)
        # MAX_RETRY_ATTEMPTS inalterado
        self.assertEqual(core.MAX_RETRY_ATTEMPTS, 3)


if __name__ == '__main__':
    unittest.main()
