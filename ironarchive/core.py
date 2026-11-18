import json, sqlite3, re, os, subprocess, shutil, urllib.request
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime, timezone

BASE=Path(__file__).resolve().parent.parent
DB=BASE/'data'/'ironarchive.sqlite3'
CONFIG=BASE/'config'/'settings.json'
ROLES=('scout','maester','artist','editor','inspector','engineer')
PREPARADO='prepared'
MAX_RETRY_ATTEMPTS=3
# Modo manual: 'done' e 'prepared' liberam a etapa seguinte; estes bloqueiam.
BLOQUEIO_MANUAL=('waiting_approval','failed','rejected','running','awaiting_integration')

def now(): return datetime.now(timezone.utc).isoformat()
def settings(): return json.loads(CONFIG.read_text(encoding='utf-8'))
@contextmanager
def connect():
 DB.parent.mkdir(exist_ok=True,parents=True)
 db=sqlite3.connect(DB);db.row_factory=sqlite3.Row
 db.execute('PRAGMA journal_mode=WAL')
 db.executescript("""CREATE TABLE IF NOT EXISTS episodes(id INTEGER PRIMARY KEY, slug TEXT UNIQUE NOT NULL,title TEXT NOT NULL,goal TEXT NOT NULL,created_at TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS jobs(id INTEGER PRIMARY KEY,episode_id INTEGER NOT NULL,role TEXT NOT NULL,kind TEXT NOT NULL,status TEXT NOT NULL,attempts INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,error TEXT,FOREIGN KEY(episode_id) REFERENCES episodes(id));
 CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,job_id INTEGER NOT NULL,event TEXT NOT NULL,at TEXT NOT NULL);""")
 db.commit()
 try:
  yield db
  db.commit()
 except:
  db.rollback()
  raise
 finally:
  db.close()

def slugify(s):
 slug=re.sub(r'[^a-z0-9]+','-',s.lower().encode('ascii','ignore').decode()).strip('-')[:48]
 return slug or 'episodio'
def episode_dir(slug):return BASE/'projects'/slug

def create_episode(title,goal):
 if not title.strip() or not goal.strip():raise ValueError('Título e objetivo obrigatórios')
 with connect() as db:
  slug=slugify(title);original=slug;n=2
  while db.execute('SELECT 1 FROM episodes WHERE slug=?',(slug,)).fetchone():slug=f'{original}-{n}';n+=1
  cur=db.execute('INSERT INTO episodes(slug,title,goal,created_at) VALUES(?,?,?,?)',(slug,title,goal,now()))
  eid=cur.lastrowid
  for role in ROLES:
   kind='render' if role=='artist' else 'review' if role=='inspector' else 'prepare'
   status='waiting_approval' if kind=='render' else 'pending'
   db.execute('INSERT INTO jobs(episode_id,role,kind,status,created_at,updated_at) VALUES(?,?,?,?,?,?)',(eid,role,kind,status,now(),now()))
  db.commit()
 folder=episode_dir(slug);folder.mkdir(parents=True,exist_ok=True)
 (folder/'episode.json').write_text(json.dumps({'id':eid,'title':title,'goal':goal,'slug':slug},ensure_ascii=False,indent=2),encoding='utf-8')
 (folder/'sources.csv').write_text('url,source_type,book_or_tv,scene,rights_notes,verified\n',encoding='utf-8')
 return eid,slug

def jobs():
 with connect() as db:return [dict(x) for x in db.execute('SELECT j.*,e.slug,e.title FROM jobs j JOIN episodes e ON e.id=j.episode_id ORDER BY j.id')]

def get_job(job_id):
    with connect() as db:
        row=db.execute('SELECT j.*,e.slug,e.title,e.goal FROM jobs j JOIN episodes e ON e.id=j.episode_id WHERE j.id=?',(job_id,)).fetchone()
        return dict(row) if row else None

def get_events(job_id,limit=200):
    with connect() as db:
        return [dict(x) for x in db.execute('SELECT * FROM events WHERE job_id=? ORDER BY id DESC LIMIT ?',(job_id,limit))]

def output_path(job):
    return episode_dir(job['slug'])/'outputs'/f"{job['id']:04d}_{job['role']}.md"

def read_output(job_id):
    job=get_job(job_id)
    if not job:return None
    f=output_path(job)
    if not f.exists():return None
    return f.read_text(encoding='utf-8')

def episodes():
    with connect() as db:
        return [dict(x) for x in db.execute('SELECT id,slug,title,created_at FROM episodes ORDER BY id')]

def change_approval(job_id,approve):
 with connect() as db:
  row=db.execute('SELECT status FROM jobs WHERE id=?',(job_id,)).fetchone()
  if not row or row['status']!='waiting_approval':raise ValueError('Job inexistente ou não aguarda aprovação')
  status='pending' if approve else 'rejected'
  db.execute('UPDATE jobs SET status=?,updated_at=? WHERE id=?',(status,now(),job_id))
  db.execute('INSERT INTO events(job_id,event,at) VALUES(?,?,?)',(job_id,'approval:'+status,now()))
  db.commit()

def _modo_producao():
    return settings().get('execution_mode','manual')!='manual'

def _condicao_predecessores():
    # Retorna (SQL, params) do filtro que decide se os predecessores liberam o job.
    if _modo_producao():
        # Producao: apenas 'done' libera etapas seguintes.
        return ("prev.status!='done'",())
    # Manual: avanca sobre 'done' e 'prepared'; bloqueia waiting_approval, failed,
    # rejected, running e awaiting_integration. Preserva aprovacoes humanas.
    placeholders=','.join('?' for _ in BLOQUEIO_MANUAL)
    return (f"prev.status IN ({placeholders})",BLOQUEIO_MANUAL)

def mark_prepared(job_id):
    """Marca um job pendente como 'prepared' (briefing manual pronto, sem execucao).

    Preserva aprovacoes humanas: apenas jobs 'pending' podem ser preparados; jobs em
    'waiting_approval' exigem decisao humana via approve/reject antes de avançar."""
    with connect() as db:
        row=db.execute('SELECT status FROM jobs WHERE id=?',(job_id,)).fetchone()
        if not row:raise ValueError('Job inexistente')
        if row['status']!='pending':raise ValueError(f'Somente jobs pendentes podem ser preparados; atual={row["status"]}')
        db.execute('UPDATE jobs SET status=?,updated_at=? WHERE id=?',(PREPARADO,now(),job_id))
        db.execute('INSERT INTO events(job_id,event,at) VALUES(?,?,?)',(job_id,'prepared:manual',now()))
        db.commit()

def run_one():
 with connect() as db:
  # Strict ordering: a later job cannot run until all earlier jobs of its episode are done.
  sql_cond,params=_condicao_predecessores()
  row=db.execute(f"""SELECT j.*,e.slug,e.title,e.goal FROM jobs j JOIN episodes e ON e.id=j.episode_id
  WHERE j.status='pending' AND NOT EXISTS(SELECT 1 FROM jobs prev WHERE prev.episode_id=j.episode_id AND prev.id<j.id AND {sql_cond})
  ORDER BY j.id LIMIT 1""",params).fetchone()
  if not row:return None
  job=dict(row)
  db.execute('UPDATE jobs SET status=?,attempts=attempts+1,updated_at=? WHERE id=?',('running',now(),job['id']))
  db.commit()
 try:
  result=execute(job)
  if result is None:
   with connect() as db:
    db.execute('UPDATE jobs SET status=?,error=?,updated_at=? WHERE id=?',('awaiting_integration','Nenhum executor real configurado; nenhuma pesquisa foi executada.',now(),job['id']))
    db.execute('INSERT INTO events(job_id,event,at) VALUES(?,?,?)',(job['id'],'awaiting_integration',now()))
   return {'id':job['id'],'role':job['role'],'status':'awaiting_integration','message':'Configure o executor Hermes; tarefa NÃO concluída.'}
  validate_result(job['role'],result)
  folder=episode_dir(job['slug'])/'outputs';folder.mkdir(exist_ok=True,parents=True)
  output=folder/f"{job['id']:04d}_{job['role']}.md"
  output.write_text(result,encoding='utf-8')
  with connect() as db:
   db.execute('UPDATE jobs SET status=?,error=NULL,updated_at=? WHERE id=?',('done',now(),job['id']))
   db.execute('INSERT INTO events(job_id,event,at) VALUES(?,?,?)',(job['id'],'completed:'+str(output),now()))
   db.commit()
  return {'id':job['id'],'role':job['role'],'output':str(output)}
 except Exception as e:
  with connect() as db:
   db.execute('UPDATE jobs SET status=?,error=?,updated_at=? WHERE id=?',('failed',str(e)[:1000],now(),job['id']))
   db.commit()
  return {'id':job['id'],'role':job['role'],'error':str(e)}

def execute(job):
 prompt=(BASE/'agents'/f"{job['role']}.md").read_text(encoding='utf-8')
 previous=episode_dir(job['slug'])/'outputs'
 prior=[]
 if previous.exists():
  for f in sorted(previous.glob('*.md')):
   prior.append(f'### {f.name}\n'+f.read_text(encoding='utf-8')[:8000])
 task=f"EPISÓDIO: {job['title']}\nOBJETIVO: {job['goal']}\n\nINSTRUÇÕES:\n{prompt}\n\nRESULTADOS ANTERIORES:\n"+('\n'.join(prior) or '(nenhum)')
 cfg=settings();hc=cfg.get('hermes',{})
 if hc.get('enabled') and cfg.get('execution_mode')=='hermes':
  # Deliberately no invented CLI flags; the operator must supply a tested argument template.
  template=hc.get('args_template')
  if not isinstance(template,list) or not template:raise RuntimeError('Configure hermes.args_template após validar a CLI; use {prompt_file}')
  taskfile=episode_dir(job['slug'])/'outputs'/f"task_{job['id']:04d}.txt"
  taskfile.parent.mkdir(exist_ok=True,parents=True);taskfile.write_text(task,encoding='utf-8')
  cmd=hc.get('command',['hermes'])+[str(x).replace('{prompt_file}',str(taskfile)) for x in template]
  proc=subprocess.run(cmd,capture_output=True,text=True,timeout=min(int(hc.get('timeout_seconds',120)),1800),shell=False,encoding='utf-8',errors='replace')
  if proc.returncode:raise RuntimeError(f'Hermes saiu com código {proc.returncode}: {proc.stderr[-700:]}')
  if not proc.stdout.strip():raise RuntimeError('Hermes não produziu saída')
  return proc.stdout
 return None

def reset_stale():
 with connect() as db:
  count=db.execute("UPDATE jobs SET status='pending',updated_at=? WHERE status='running'",(now(),)).rowcount
  db.commit();return count

def doctor():
 cfg=settings();out={'python':os.sys.version.split()[0],'paths':{},'tools':{},'comfyui':None,'hermes_mode':cfg.get('execution_mode')}
 for key,path in cfg.get('paths',{}).items():out['paths'][key]={'path':path,'exists':Path(path).exists()}
 for exe in ('python','hermes','ffmpeg','ffprobe','git','nvidia-smi'):out['tools'][exe]=shutil.which(exe)
 if cfg.get('comfyui',{}).get('enabled'):
  url=cfg['comfyui']['url'].rstrip('/')+'/system_stats'
  try:
   with urllib.request.urlopen(url,timeout=3) as response:out['comfyui']= {'reachable':True,'status':response.status}
  except Exception as e:out['comfyui']={'reachable':False,'error':str(e)}
 return out


def validate_result(role, result):
 if not result or len(result.strip()) < 250:
  raise ValueError('Saída insuficiente: não será marcada como concluída')
 if 'tarefa preparada' in result.lower() or 'nenhum fato de lore' in result.lower():
  raise ValueError('Saída é apenas um placeholder')
 if role=='scout':
  low=result.lower()
  for section in ('evidências','plano','pendências','próxima ação'):
   if section not in low:raise ValueError('Scout sem seção obrigatória: '+section)
  if not re.search(r'https?://[^\s)<>]+',result):
   raise ValueError('Scout sem URLs de fontes verificáveis; não marcar como done')

def repair_placeholder_jobs():
 """Migra somente jobs antigos cujo output declara explicitamente ser placeholder."""
 count=0
 with connect() as db:
  rows=db.execute("SELECT j.id,j.role,e.slug FROM jobs j JOIN episodes e ON e.id=j.episode_id WHERE j.status='done'").fetchall()
  for row in rows:
   f=episode_dir(row['slug'])/'outputs'/f"{row['id']:04d}_{row['role']}.md"
   if f.exists() and 'tarefa preparada' in f.read_text(encoding='utf-8').lower():
    db.execute("UPDATE jobs SET status='awaiting_integration',error=?,updated_at=? WHERE id=?",('Placeholder anterior; aguardando integração real',now(),row['id']))
    db.execute('INSERT INTO events(job_id,event,at) VALUES(?,?,?)',(row['id'],'placeholder_reclassified',now()))
    count+=1
 return count

def retry_integration():
    """Reintegra jobs em 'awaiting_integration' de volta para 'pending'."""
    with connect() as db:
        n=db.execute("UPDATE jobs SET status='pending',error=NULL,updated_at=? WHERE status='awaiting_integration'",(now(),)).rowcount
    return n

def retry_failed(job_id, confirm=False):
    """Recoloca um job 'failed' em 'pending' para nova tentativa.

    Apenas jobs em 'failed' são elegíveis. Não executa o pipeline automaticamente;
    apenas libera o job para a próxima execução de run_one(), que respeitará a
    ordem de predecessores.

    Preserva o contador 'attempts' (não zera) e o usa para o limite de tentativas.
    Registra evento de auditoria com status anterior, erro anterior e timestamp.
    A transação é atômica (UPDATE ... WHERE status='failed') para impedir retries
    duplicados em chamadas concorrentes.
    """
    if not confirm:
        raise ValueError('Confirmação explícita requerida para retry')

    max_attempts = settings().get('safety', {}).get('max_retry_attempts', MAX_RETRY_ATTEMPTS)

    with connect() as db:
        row = db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
        if not row:
            raise ValueError('Job inexistente')
        if row['status'] != 'failed':
            raise ValueError(f'Somente jobs falhados podem ser retryados; atual={row["status"]}')

        # Limite de tentativas: contador acumulado (não zera).
        if row['attempts'] >= max_attempts:
            raise ValueError(
                f'Limite de tentativas atingido ({row["attempts"]}/{max_attempts})'
            )

        # Checagem de dependências: predecessores devem estar liberados.
        sql_cond, params = _condicao_predecessores()
        bloqueado = db.execute(
            f"""SELECT 1 FROM jobs prev
                WHERE prev.episode_id=? AND prev.id<? AND {sql_cond}""",
            (row['episode_id'], row['id'], *params)
        ).fetchone()
        if bloqueado:
            raise ValueError('Dependências do episódio não liberadas para retry')

        previous_status = row['status']
        previous_error = row['error']

        # UPDATE atômico: só prossegue se ainda estiver em 'failed'.
        cur = db.execute(
            "UPDATE jobs SET status='pending', error=NULL, updated_at=? WHERE id=? AND status='failed'",
            (now(), job_id)
        )
        if cur.rowcount == 0:
            raise ValueError('Job não está mais em falhou (alterado por outra transação)')

        db.execute(
            'INSERT INTO events(job_id,event,at) VALUES(?,?,?)',
            (job_id,
             f'retry: {previous_status}->pending (erro anterior: {previous_error or "—"})',
             now())
        )
        db.commit()

    return {
        'id': job_id,
        'status': 'pending',
        'previous_status': previous_status,
        'previous_error': previous_error,
        'attempts': row['attempts'],
        'max_attempts': max_attempts,
    }
