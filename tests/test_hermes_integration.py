import tempfile
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

from ironarchive import core

ROLES = core.ROLES


def _make_env(t, execution_mode='manual'):
    agents = Path(t) / 'agents'
    agents.mkdir()
    for role in ROLES:
        (agents / f'{role}.md').write_text('Instruções de teste', encoding='utf-8')
    patches = [
        patch.object(core, 'DB', Path(t) / 'data' / 'integration.db'),
        patch.object(core, 'BASE', Path(t)),
        patch.object(core, 'settings', return_value={
            'execution_mode': execution_mode,
            'hermes': {'enabled': True, 'timeout_seconds': 120},
        }),
    ]
    for p in patches:
        p.start()
    return patches


def _stop_patches(patches):
    for p in reversed(patches):
        p.stop()


def _proc(returncode=0, stdout='', stderr=''):
    m = MagicMock()
    m.returncode = returncode
    m.stdout = stdout
    m.stderr = stderr
    return m


class TestHermesIntegration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patches = _make_env(self.tmp.name)

    def tearDown(self):
        _stop_patches(self.patches)
        self.tmp.cleanup()

    def _status(self, job_id):
        with core.connect() as db:
            row = db.execute("SELECT status,error FROM jobs WHERE id=?", (job_id,)).fetchone()
        return dict(row) if row else None

    def _hermes_settings(self):
        return {
            'execution_mode': 'hermes',
            'hermes': {
                'enabled': True, 'command': ['hermes'], 'timeout_seconds': 120,
                'args_template': ['chat', '--query-file', '{prompt_file}', '--oneshot',
                                  '--quiet', '--format', 'text', '--max-turns', '6',
                                  '--run-budget', '150', '--source', 'tool'],
            },
        }

    def _write_taskfile(self, slug, job_id):
        out_dir = Path(self.tmp.name) / 'projects' / slug / 'outputs'
        out_dir.mkdir(parents=True, exist_ok=True)
        tf = out_dir / f"task_{job_id:04d}.txt"
        tf.write_text('prompt de teste', encoding='utf-8')

    # 1. subprocesso falha (returncode != 0) -> run_one marca failed, stderr capturado
    def test_run_one_subprocess_failure_marks_failed(self):
        with patch.object(core, 'settings', return_value=self._hermes_settings()):
            core.create_episode('Episodio Teste', 'Objetivo de teste')
            slug = 'episodio-teste'
            self._write_taskfile(slug, 1)
            with patch('subprocess.run', return_value=_proc(returncode=1, stderr='session_id: local-xxx')):
                res = core.run_one()
            self.assertEqual(res['role'], 'scout')
            self.assertIn('error', res)
            self.assertIn('session_id', res['error'])
        st = self._status(1)
        self.assertEqual(st['status'], 'failed')
        self.assertIsNotNone(st['error'])

    # 2. stdout vazio -> run_one marca failed
    def test_run_one_empty_stdout_marks_failed(self):
        with patch.object(core, 'settings', return_value=self._hermes_settings()):
            core.create_episode('Episodio Teste', 'Objetivo de teste')
            slug = 'episodio-teste'
            self._write_taskfile(slug, 1)
            with patch('subprocess.run', return_value=_proc(returncode=0, stdout='', stderr='')):
                res = core.run_one()
            self.assertEqual(res['role'], 'scout')
            self.assertIn('error', res)
            self.assertIn('não produziu saída', res['error'])
        st = self._status(1)
        self.assertEqual(st['status'], 'failed')

    # 3. excecao do subprocesso (FileNotFoundError) -> run_one marca failed
    def test_run_one_subprocess_exception_marks_failed(self):
        with patch.object(core, 'settings', return_value=self._hermes_settings()):
            core.create_episode('Episodio Teste', 'Objetivo de teste')
            slug = 'episodio-teste'
            self._write_taskfile(slug, 1)
            with patch('subprocess.run', side_effect=FileNotFoundError('hermes nao encontrado')):
                res = core.run_one()
            self.assertEqual(res['role'], 'scout')
            self.assertIn('error', res)
            self.assertIn('hermes nao encontrado', res['error'])
        st = self._status(1)
        self.assertEqual(st['status'], 'failed')

    # 4. validate_result rejeita placeholders, saídas curtas e scout sem evidências
    def test_validate_result_rejects_invalid_outputs(self):
        with self.assertRaises(ValueError):
            core.validate_result('scout', '# SCOUT — tarefa preparada\n\nnada mais.')
        with self.assertRaises(ValueError):
            core.validate_result('scout', 'OK')
        with self.assertRaises(ValueError):
            core.validate_result('maester', 'nenhum fato de lore encontrado sobre o tema.')
        with self.assertRaises(ValueError):
            core.validate_result('scout', 'Apenas um texto qualquer sem secoes necessarias.')
        short_but_long = ('x' * 300 + '\n## Evidências\n## Plano\n## Pendências\n## Próxima ação\n')
        with self.assertRaises(ValueError):
            core.validate_result('scout', short_but_long)
        valid_scout = ('## Evidências\nhttps://exemplo.com/fonte\n## Plano\nplano\n'
                       '## Pendências\npendente\n## Próxima ação\nacao\n' + 'y' * 300)
        core.validate_result('scout', valid_scout)
        with self.assertRaises(ValueError):
            core.validate_result('maester', 'curto')

    # 5. run_one nunca marca done sem pipeline real (executor Hermes configurado)
    def test_run_one_never_marks_done_without_real_executor(self):
        # modo manual: executor real nao configurado -> awaiting_integration, nunca done
        with patch.object(core, 'settings', return_value={
            'execution_mode': 'manual', 'hermes': {'enabled': False},
        }):
            core.create_episode('Episodio Teste', 'Objetivo de teste')
            res = core.run_one()
            self.assertEqual(res['role'], 'scout')
            self.assertEqual(res['status'], 'awaiting_integration')
            self.assertEqual(self._status(1)['status'], 'awaiting_integration')
            self.assertNotEqual(self._status(1)['status'], 'done')

        # modo hermes com executor real configurado e saída valida -> done
        core.create_episode('Episodio Teste 2', 'Objetivo de teste 2')
        slug2 = 'episodio-teste-2'
        self._write_taskfile(slug2, 7)
        valido = ('## Evidências\nhttps://exemplo.com/fonte\n## Plano\nplano\n'
                  '## Pendências\npendente\n## Próxima ação\nacao\n' + 'z' * 300)
        with patch.object(core, 'settings', return_value=self._hermes_settings()):
            with patch('subprocess.run', return_value=_proc(returncode=0, stdout=valido, stderr='')):
                res = core.run_one()
            self.assertEqual(res['role'], 'scout')
            self.assertIn('output', res)
        st = self._status(7)
        self.assertEqual(st['status'], 'done')


    def test_execute_nao_inclui_placeholder_antigo_no_contexto(self):
        with patch.object(core, 'settings', return_value=self._hermes_settings()):
            core.create_episode('Episodio Contexto', 'Objetivo de teste')
            slug = 'episodio-contexto'
            with core.connect() as db:
                db.execute("UPDATE jobs SET status='done', error=NULL WHERE id=1")
                db.commit()
            out_dir = Path(self.tmp.name) / 'projects' / slug / 'outputs'
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / '0001_scout.md').write_text('# SCOUT — tarefa preparada\n\nplaceholder antigo rejeitado.', encoding='utf-8')
            self._write_taskfile(slug, 1)
            with patch('subprocess.run', return_value=_proc(returncode=0, stdout='saida valida do hermes', stderr='')):
                res = core.execute(core.get_job(1))
            task = (out_dir / 'task_0001.txt').read_text(encoding='utf-8')
            self.assertNotIn('tarefa preparada', task)
            self.assertNotIn('placeholder antigo', task)
            self.assertIn('RESULTADOS ANTERIORES', task)
            self.assertIn('(nenhum)', task)

    def test_execute_inclui_resultado_legitimo_do_predecessor(self):
        with patch.object(core, 'settings', return_value=self._hermes_settings()):
            core.create_episode('Episodio Legitimo', 'Objetivo de teste')
            slug = 'episodio-legitimo'
            valido = ('## Evidências\nhttps://exemplo.com/fonte\n## Plano\nplano\n## Pendências\npendente\n## Próxima ação\nacao\n' + 'x' * 300)
            with core.connect() as db:
                db.execute("UPDATE jobs SET status='done', error=NULL WHERE id=1")
                db.commit()
            out_dir = Path(self.tmp.name) / 'projects' / slug / 'outputs'
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / '0001_scout.md').write_text(valido, encoding='utf-8')
            job2 = core.get_job(2)
            self._write_taskfile(slug, 2)
            with patch('subprocess.run', return_value=_proc(returncode=0, stdout='saida maester', stderr='')):
                res = core.execute(job2)
            task = (out_dir / 'task_0002.txt').read_text(encoding='utf-8')
            self.assertIn('Evidências', task)
            self.assertIn('https://exemplo.com/fonte', task)

    def test_run_one_stdout_placeholder_marca_failed_sem_done(self):
        with patch.object(core, 'settings', return_value=self._hermes_settings()):
            core.create_episode('Episodio Placeholder', 'Objetivo de teste')
            slug = 'episodio-placeholder'
            self._write_taskfile(slug, 1)
            placeholder_saida = '# SCOUT — tarefa preparada\n\n' + 'nenhum fato de lore gerado. ' * 20
            with patch('subprocess.run', return_value=_proc(returncode=0, stdout=placeholder_saida, stderr='')):
                res = core.run_one()
            self.assertIn('error', res)
            self.assertIn('placeholder', res['error'].lower())
            st = self._status(1)
            self.assertEqual(st['status'], 'failed')
            self.assertNotEqual(st['status'], 'done')

if __name__ == '__main__':
    unittest.main()
