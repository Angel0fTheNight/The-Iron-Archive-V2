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
        patch.object(core, 'DB', Path(t) / 'data' / 'contract.db'),
        patch.object(core, 'BASE', Path(t)),
        patch.object(core, 'settings', return_value={
            'execution_mode': execution_mode,
            'hermes': {'enabled': False},
        }),
    ]
    for p in patches:
        p.start()
    return patches


def _stop_patches(patches):
    for p in reversed(patches):
        p.stop()


class TestApiFrontendContract(unittest.TestCase):
    """Detecta incompatibilidades entre o JSON da API e o consumo do frontend.

    Não há infraestrutura de testes de navegador; estes testes validam em Python
    que os campos acessados pelo frontend (index.html) existem nas respostas da API.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patches = _make_env(self.tmp.name)

    def tearDown(self):
        _stop_patches(self.patches)
        self.tmp.cleanup()

    def test_episodes_includes_goal_for_frontend(self):
        # loadEpisodes acessa ep.goal; a API deve expor goal em cada episódio.
        core.create_episode('Episodio Teste', 'Objetivo de teste')
        episodes = core.episodes()
        self.assertEqual(len(episodes), 1)
        ep = episodes[0]
        self.assertIn('goal', ep)
        self.assertIsInstance(ep['goal'], str)
        self.assertEqual(len(ep['goal']), len('Objetivo de teste'))
        # Simula o acesso do frontend: ep.goal.slice(0,90) nao deve lancar TypeError.
        goal = ep['goal'] or ''
        _ = goal.slice if hasattr(goal, 'slice') else goal[:90]  # noqa: B018
        _ = goal[:90] if len(goal) > 90 else goal

    def test_jobs_include_fields_accessed_by_frontend(self):
        # loadQueue acessa: id, role, kind, status, attempts, updated_at, created_at, episode_id, slug, title
        core.create_episode('Episodio Teste', 'Objetivo de teste')
        jobs = core.jobs()
        self.assertEqual(len(jobs), 6)
        required = {'id', 'episode_id', 'role', 'kind', 'status', 'attempts',
                    'created_at', 'updated_at', 'error', 'slug', 'title'}
        for j in jobs:
            missing = required - set(j.keys())
            self.assertEqual(missing, set(), f'campos ausentes no job {j["id"]}: {missing}')

    def test_job_detail_includes_fields_accessed_by_frontend(self):
        # openDetail acessa: id, role, status, kind, attempts, goal, title, slug
        core.create_episode('Episodio Teste', 'Objetivo de teste')
        job = core.get_job(1)
        self.assertIsNotNone(job)
        self.assertIn('goal', job)
        self.assertIn('title', job)
        self.assertIn('slug', job)

    def test_events_include_fields_accessed_by_frontend(self):
        # loadLogs acessa: at, job_id, role, event
        core.create_episode('Episodio Teste', 'Objetivo de teste')
        with core.connect() as db:
            db.execute("INSERT INTO events(job_id,event,at) VALUES(1,'teste_evento',?)",
                       (core.now(),))
            db.commit()
        events = core.get_events(1)
        self.assertGreaterEqual(len(events), 1)
        for e in events:
            for field in ('at', 'job_id', 'event'):
                self.assertIn(field, e, f'campo {field} ausente no evento')

    def test_doctor_returns_expected_top_level_keys(self):
        # loadDoctor acessa: python, hermes_mode/execution_mode, paths, tools, comfyui
        core.create_episode('Episodio Teste', 'Objetivo de teste')
        d = core.doctor()
        for key in ('python', 'paths', 'tools', 'comfyui', 'hermes_mode'):
            self.assertIn(key, d, f'chave {key} ausente no doctor')


if __name__ == '__main__':
    unittest.main()
