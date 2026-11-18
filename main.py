import argparse,json,sys
from ironarchive.core import create_episode,jobs,change_approval,run_one,reset_stale,doctor,repair_placeholder_jobs,retry_integration,mark_prepared,retry_exceptional

def main(argv=None):
 p=argparse.ArgumentParser(description='THE IRON ARCHIVE 2.0')
 sub=p.add_subparsers(dest='cmd',required=True)
 sub.add_parser('doctor');sub.add_parser('status');sub.add_parser('reset-stale');sub.add_parser('repair-placeholders');sub.add_parser('retry-integration')
 re=sub.add_parser('retry-exceptional');re.add_argument('--job',type=int,required=True);re.add_argument('--confirm',action='store_true');re.add_argument('--justificativa',type=str,default='');re.add_argument('--autorizador',type=str,default='')
 n=sub.add_parser('new');n.add_argument('--title',required=True);n.add_argument('--goal',required=True)
 r=sub.add_parser('run');r.add_argument('--steps',type=int,default=1)
 pr=sub.add_parser('prepare');pr.add_argument('--job',type=int,required=True)
 for name in ('approve','reject'):
  x=sub.add_parser(name);x.add_argument('--job',type=int,required=True)
 args=p.parse_args(argv)
 try:
  if args.cmd=='doctor':print(json.dumps(doctor(),indent=2,ensure_ascii=False))
  elif args.cmd=='new':print('Episódio criado:',create_episode(args.title,args.goal))
  elif args.cmd=='status':
   for j in jobs():print(f"#{j['id']:03} | {j['slug'][:25]:25} | {j['role']:10} | {j['status']:18} | tentativas {j['attempts']}")
  elif args.cmd=='run':
   for _ in range(max(0,min(args.steps,100))):
    result=run_one()
    if result is None:print('Nenhuma etapa pronta. Verifique aprovações ou etapas anteriores.');break
    print(json.dumps(result,ensure_ascii=False))
  elif args.cmd=='reset-stale':print('Jobs recuperados:',reset_stale())
  elif args.cmd=='repair-placeholders':print('Placeholders reclassificados:',repair_placeholder_jobs())
  elif args.cmd=='retry-integration':print('Jobs liberados para nova tentativa:',retry_integration())
  elif args.cmd=='retry-exceptional':print('Recuperação excepcional:',retry_exceptional(args.job,confirm=args.confirm,justificativa=args.justificativa,autorizador=args.autorizador))
  elif args.cmd=='prepare':mark_prepared(args.job);print('Job preparado (briefing manual).')
  else:change_approval(args.job,args.cmd=='approve');print('Decisão registrada.')
 except Exception as e:print('ERRO:',e,file=sys.stderr);return 1
 return 0
if __name__=='__main__':sys.exit(main())
