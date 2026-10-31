#!/usr/bin/env bash
# P-1: this is the only harness permitted to start the scratch Redis server.
set -euo pipefail
recap_root="$(cd "$(dirname "$0")/.." && pwd)"
recap_poc="$recap_root"
if [[ -d "$recap_root/legacy/lua" ]]; then recap_poc="$recap_root/legacy"; fi
recap_python="$recap_root/.venv/bin/python"
if [[ ! -x "$recap_python" ]]; then recap_python=python3; fi
recap_server="/opt/homebrew/bin/redis-server"
recap_cli="/opt/homebrew/bin/redis-cli"
if [[ ! -x "$recap_server" ]]; then recap_server="$(command -v redis-server)"; fi
if [[ ! -x "$recap_cli" ]]; then recap_cli="$(command -v redis-cli)"; fi
"$recap_server" --version | grep -q 'v=8\.' || { echo 'BLOCKED: requires Redis 8.x' >&2; exit 2; }
if "$recap_cli" -h 127.0.0.1 -p 6390 ping 2>/dev/null | grep -q PONG; then
  echo 'BLOCKED: port 6390 already in use; existing service left untouched' >&2
  exit 2
fi
recap_temp="$(mktemp -d)"
recap_pid=''
recap_owned=0
cleanup() {
  if [[ "$recap_owned" == 1 ]]; then
    "$recap_cli" -h 127.0.0.1 -p 6390 shutdown nosave >/dev/null 2>&1 || true
  fi
  if [[ -n "$recap_pid" ]]; then wait "$recap_pid" 2>/dev/null || true; fi
  rm -rf "$recap_temp"
}
trap cleanup EXIT
"$recap_server" --bind 127.0.0.1 --port 6390 --save "" --appendonly no --dir "$recap_temp" >"$recap_temp/server.log" 2>&1 &
recap_pid=$!
for ((recap_attempt=0; recap_attempt<50; recap_attempt++)); do
  if ! kill -0 "$recap_pid" 2>/dev/null; then
    cat "$recap_temp/server.log" >&2
    echo 'BLOCKED: port bind' >&2
    exit 2
  fi
  if "$recap_cli" -h 127.0.0.1 -p 6390 ping 2>/dev/null | grep -q PONG; then
    recap_actual_pid="$("$recap_cli" -h 127.0.0.1 -p 6390 --raw INFO server | tr -d '\r' | sed -n 's/^process_id://p')"
    if [[ "$recap_actual_pid" != "$recap_pid" ]]; then
      echo 'BLOCKED: scratch Redis ownership mismatch' >&2
      exit 2
    fi
    recap_owned=1
    break
  fi
  sleep 0.1
done
if [[ "$recap_owned" != 1 ]]; then echo 'BLOCKED: Redis readiness timeout' >&2; exit 2; fi
"$recap_python" - "$recap_root" "$recap_poc" "$recap_cli" <<'PY'
from argparse import Namespace
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import re
import subprocess
import sys

root,poc=map(Path,sys.argv[1:3]);cli=sys.argv[3]
sys.path.insert(0,str(root/'src'))
from recap.constraints import violations
from recap.model import capacity
from recap.planner.create import plan as create
from recap.planner.upscale import plan as upscale
from recap.planner.optimize import plan as optimize
from recap.verifier import verify

def command(*args):
    result=subprocess.run([cli,'-h','127.0.0.1','-p','6390','--raw',*map(str,args)],check=True,capture_output=True,text=True)
    if result.stdout.startswith(('ERR ','WRONGTYPE ','NOSCRIPT ')):
        raise RuntimeError(result.stdout)
    return result.stdout.strip()

loaded=subprocess.run(['bash',str(poc/'initcapaplan-test.sh'),'-r','127.0.0.1','-p','6390'],cwd=poc,capture_output=True,text=True,check=True)
assert command('ZCARD','nodes')=='5'
assert command('SCARD','shards')=='8'
lua=(poc/'lua/capaplan.lua').read_text()
snapshot=json.loads((root/'tests/fixtures/poc-5-nodes.json').read_text())
baseline=violations(snapshot)
cases=[]

def run(*args):
    return command('EVAL',lua,0,*args)

def counterfactual_matches(case,state):
    kind=case['command']
    if kind=='can-create':
        result=create(state,**case['args'])
        matched=result['verdict']==case['verdict']
    elif kind=='can-upscale':
        result=upscale(state,**case['args'])
        matched=result['verdict'] in {2:{'feasible'},1:{'feasible','feasible-in-steps'},0:{'infeasible'}}[case['poc_score']]
    elif kind=='optimize':
        options=Namespace(scope='node',db=None,rack=None,level=1,need=None,reserve_shard_size=None,explain=False,**case['args'])
        result=optimize(state,options)
        matched=[[s['shard_uid'],s['from_node'],s['to_node']] for s in result['plan']]==case['moves']
    else:
        return False
    verify(state,result['plan'],result.get('goal') if result['verdict'] in ('feasible','feasible-in-steps','goal-met') else None)
    return matched

def record(case,equal):
    if not equal:
        counterfactual=deepcopy(snapshot)
        uids=sorted({v.bdb_uid for v in baseline if v.code=='rack-awareness'})
        for db in counterfactual['bdbs']:
            if db['uid'] in uids:db['rack_aware']=False
        if baseline and all(v.code=='rack-awareness' for v in baseline) and not violations(counterfactual) and counterfactual_matches(case,counterfactual):
            case['divergence_reason']='F-8'
            case['divergence_evidence']='The original snapshot has a per-database rack violation. Changing only the affected database rack_aware policy to false makes this exact case match the recorded POC verdict or move list; all counterfactual plan steps pass replay. The actual snapshot remains unchanged. '+ '; '.join(map(str,baseline))
            case['divergence_proof']=dict(method='per-database-rack-counterfactual',database_uids=uids)
        else:
            raise RuntimeError('Unclassified P-1 divergence: '+json.dumps(case))
    cases.append(case)

for size in (1,5,25):
    argv=['CAPA',str(size)];output=run(*argv)
    value=int(command('GET',f'capacity:cluster:{size}G'))
    case=dict(command='capacity',args={'size':size*2**30},poc_argv=argv,poc_output=output,capacity=value)
    record(case,capacity(snapshot,[size*2**30])['cluster'][0]['capacity']==value)
for size,count in ((10,1),(50,1),(100,2),(200,4)):
    argv=['CANCREATE',str(size),str(count),'true'];output=run(*argv)
    verdict='feasible' if command('GET',f'cancreate:{size}G')=='true' else 'infeasible'
    args=dict(memory=size*2**30,shards=count,replication=True)
    record(dict(command='can-create',args=args,poc_argv=argv,poc_output=output,verdict=verdict),create(snapshot,**args)['verdict']==verdict)
output=run('CORR')
for uid,size,count in ((1,10,1),(2,100,2),(4,50,1),(5,50,1)):
    score=int(float(command('ZSCORE','db:canUpscale',f'db:{uid}')))
    args=dict(db_uid=str(uid),memory=size*2**30,shards=count)
    actual=upscale(snapshot,**args)['verdict']
    expected={2:{'feasible'},1:{'feasible','feasible-in-steps'},0:{'infeasible'}}[score]
    record(dict(command='can-upscale',args=args,poc_argv=['CORR'],poc_output=output,poc_score=score),actual in expected)
for uid in range(1,6):
    argv=['O','N',f'node:{uid}','1','25','25'];output=run(*argv)
    tasks=command('LRANGE','temp:optimise:task',0,-1)
    moves=[]
    for line in tasks.splitlines():
        match=re.fullmatch(r'rladmin migrate shard (\d+) preserve_roles target_node (\d+)',line)
        if not match:raise RuntimeError('Unparsed POC move: '+line)
        moves.append([int(match[1]),uid,int(match[2])])
    args=dict(node=str(uid),shard_size_min=2**30,shard_size_max=25*2**30,shard_used_max=25*2**30)
    options=Namespace(scope='node',db=None,rack=None,level=1,need=None,reserve_shard_size=None,explain=False,**args)
    actual=optimize(snapshot,options)
    actual_moves=[[s['shard_uid'],s['from_node'],s['to_node']] for s in actual['plan']]
    record(dict(command='optimize',args=args,poc_argv=argv,poc_output=output,moves=moves),actual_moves==moves)
version=command('INFO','server').split('redis_version:',1)[1].splitlines()[0]
target=root/'tests/fixtures/poc-parity.json'
target.write_text(json.dumps(dict(schema_version=1,redis_version=version,cases=cases),indent=2)+'\n')
print(f'P-1: {len(cases)} cases recorded')
print('DIVERGENCES:',dict(Counter(c['divergence_reason'] for c in cases if c.get('divergence_reason'))))
PY
