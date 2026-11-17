import unittest,tempfile
from pathlib import Path
from unittest.mock import patch
from ironarchive import core

ROLES=core.ROLES

def _criar_agentes(t):
    (Path(t)/'agents').mkdir()
    for role in ROLES:
        (Path(t)/'agents'/f'{role}.md').write_text('Instruções de teste',encoding='utf-8')

def _definir_status(job_id,status):
    with core.connect() as db:
        db.execute("UPDATE jobs SET status=?,updated_at=? WHERE id=?",(status,core.now(),job_id))
        db.commit()

class TestCore(unittest.TestCase):
 def test_slug(self):self.assertEqual(core.slugify('Jaime Lannister?!'),'jaime-lannister')
 def test_pipeline(self):
  with tempfile.TemporaryDirectory() as t:
   with patch.object(core,'DB',Path(t)/'data'/'test.db'),patch.object(core,'BASE',Path(t)):
    (Path(t)/'agents').mkdir()
    for role in core.ROLES:(Path(t)/'agents'/f'{role}.md').write_text('Instruções de teste',encoding='utf-8')
    with patch.object(core,'settings',return_value={'execution_mode':'manual','hermes':{'enabled':False}}):
     eid,slug=core.create_episode('Teste Jaime','Explicar motivo')
     self.assertEqual(len(core.jobs()),6)
     self.assertEqual(core.jobs()[2]['status'],'waiting_approval')
     self.assertEqual(core.run_one()['role'],'scout')
     # sem executor real o scout nao fica done: bloqueia a dependencia seguinte
     self.assertIsNone(core.run_one())
     # aprovacao humana se aplica apenas a waiting_approval (artista); scout nao e elegivel
     with self.assertRaises(ValueError):core.change_approval(1,True)
     # preparacao manual do maester (pendente) o deixa pronto, sem executar
     core.mark_prepared(2)
     # maester esta prepared (nao pendente) e artista continua waiting_approval: nada a executar
     self.assertIsNone(core.run_one())
 def test_approval(self):
  with tempfile.TemporaryDirectory() as t:
   with patch.object(core,'DB',Path(t)/'data'/'test.db'),patch.object(core,'BASE',Path(t)):
    core.create_episode('Outro','Objetivo')
    with self.assertRaises(ValueError):core.change_approval(1,True)
 def test_manual_avanca_sobre_prepared_e_done(self):
     # manual: 'done' e 'prepared' liberam; 'prepared' nao e reexecutado pelo run_one
     with tempfile.TemporaryDirectory() as t:
         with patch.object(core,'DB',Path(t)/'data'/'test.db'),patch.object(core,'BASE',Path(t)),patch.object(core,'settings',return_value={'execution_mode':'manual','hermes':{'enabled':False}}):
             _criar_agentes(t)
             core.create_episode('Episodio Teste','Objetivo de teste')
             with core.connect() as db:
                 db.execute("UPDATE jobs SET status='done' WHERE id=1")
                 db.execute("UPDATE jobs SET status='prepared' WHERE id=2")
                 db.execute("UPDATE jobs SET status='done' WHERE id=3")
                 db.commit()
             res=core.run_one()
             self.assertEqual(res['role'],'editor')

 def test_manual_bloqueia_predecessores(self):
     for bloqueante in ('waiting_approval','failed','rejected','running','awaiting_integration'):
         with tempfile.TemporaryDirectory() as t:
             with patch.object(core,'DB',Path(t)/'data'/'test.db'),patch.object(core,'BASE',Path(t)),patch.object(core,'settings',return_value={'execution_mode':'manual','hermes':{'enabled':False}}):
                 _criar_agentes(t)
                 core.create_episode('Episodio Teste','Objetivo de teste')
                 with core.connect() as db:
                     db.execute("UPDATE jobs SET status='done' WHERE id=1")
                     db.execute(f"UPDATE jobs SET status='{bloqueante}' WHERE id=2")
                     db.execute("UPDATE jobs SET status='done' WHERE id=3")
                     db.commit()
                 self.assertIsNone(core.run_one())

 def test_manual_nao_bloqueia_prepared_nor_done(self):
     for liberador in ('done','prepared'):
         with tempfile.TemporaryDirectory() as t:
             with patch.object(core,'DB',Path(t)/'data'/'test.db'),patch.object(core,'BASE',Path(t)),patch.object(core,'settings',return_value={'execution_mode':'manual','hermes':{'enabled':False}}):
                 _criar_agentes(t)
                 core.create_episode('Episodio Teste','Objetivo de teste')
                 with core.connect() as db:
                     db.execute("UPDATE jobs SET status='done' WHERE id=1")
                     db.execute(f"UPDATE jobs SET status='{liberador}' WHERE id=2")
                     db.execute("UPDATE jobs SET status='done' WHERE id=3")
                     db.commit()
                 res=core.run_one()
                 self.assertEqual(res['role'],'editor')

 def test_production_apenas_done_libera(self):
     # producao: 'prepared' nao libera etapas seguintes
     with tempfile.TemporaryDirectory() as t:
         with patch.object(core,'DB',Path(t)/'data'/'test.db'),patch.object(core,'BASE',Path(t)),patch.object(core,'settings',return_value={'execution_mode':'production','hermes':{'enabled':False}}):
             _criar_agentes(t)
             core.create_episode('Episodio Teste','Objetivo de teste')
             with core.connect() as db:
                 db.execute("UPDATE jobs SET status='done' WHERE id=1")
                 db.execute("UPDATE jobs SET status='prepared' WHERE id=2")
                 db.execute("UPDATE jobs SET status='done' WHERE id=3")
                 db.commit()
             self.assertIsNone(core.run_one())

 def test_production_libera_quando_todos_done(self):
     with tempfile.TemporaryDirectory() as t:
         with patch.object(core,'DB',Path(t)/'data'/'test.db'),patch.object(core,'BASE',Path(t)),patch.object(core,'settings',return_value={'execution_mode':'production','hermes':{'enabled':False}}):
             _criar_agentes(t)
             core.create_episode('Episodio Teste','Objetivo de teste')
             with core.connect() as db:
                 db.execute("UPDATE jobs SET status='done' WHERE id=1")
                 db.execute("UPDATE jobs SET status='done' WHERE id=2")
                 db.execute("UPDATE jobs SET status='done' WHERE id=3")
                 db.commit()
             res=core.run_one()
             self.assertEqual(res['role'],'editor')

 def test_mark_prepared_de_pendente(self):
     with tempfile.TemporaryDirectory() as t:
         with patch.object(core,'DB',Path(t)/'data'/'test.db'),patch.object(core,'BASE',Path(t)),patch.object(core,'settings',return_value={'execution_mode':'manual','hermes':{'enabled':False}}):
             _criar_agentes(t)
             core.create_episode('Episodio Teste','Objetivo de teste')
             core.mark_prepared(2)
             with core.connect() as db:
                 st=db.execute("SELECT status FROM jobs WHERE id=2").fetchone()['status']
             self.assertEqual(st,'prepared')

 def test_mark_prepared_nao_bypassa_aprovacao(self):
     # artista nasce em waiting_approval: nao pode ser preparado sem decisao humana
     with tempfile.TemporaryDirectory() as t:
         with patch.object(core,'DB',Path(t)/'data'/'test.db'),patch.object(core,'BASE',Path(t)),patch.object(core,'settings',return_value={'execution_mode':'manual','hermes':{'enabled':False}}):
             _criar_agentes(t)
             core.create_episode('Episodio Teste','Objetivo de teste')
             with self.assertRaises(ValueError):core.mark_prepared(3)

 def test_mark_prepared_apenas_pendente(self):
     with tempfile.TemporaryDirectory() as t:
         with patch.object(core,'DB',Path(t)/'data'/'test.db'),patch.object(core,'BASE',Path(t)),patch.object(core,'settings',return_value={'execution_mode':'manual','hermes':{'enabled':False}}):
             _criar_agentes(t)
             core.create_episode('Episodio Teste','Objetivo de teste')
             _definir_status(1,'done')
             _definir_status(2,'failed')
             with self.assertRaises(ValueError):core.mark_prepared(1)
             with self.assertRaises(ValueError):core.mark_prepared(2)

if __name__=='__main__':unittest.main()
