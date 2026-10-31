"""P-1 recorded parity; CI never starts Redis."""
from argparse import Namespace
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
ALLOWED={f'F-{i}' for i in range(1,16)}|{'rounding','live-ranking','tie-break'}


def test_p1_recorded_parity_and_inventory():
    from recap.model import capacity
    from recap.planner.create import plan as create
    from recap.planner.upscale import plan as upscale
    from recap.planner.optimize import plan as optimize
    from recap.verifier import verify
    snapshot=json.loads((ROOT/'tests/fixtures/poc-5-nodes.json').read_text())
    data=json.loads((ROOT/'tests/fixtures/poc-parity.json').read_text())
    assert data['redis_version'].startswith('8.')
    counts={command:0 for command in ('capacity','can-create','can-upscale','optimize')}
    for case in data['cases']:
        command=case['command'];counts[command]+=1
        assert case['poc_argv'] and 'poc_output' in case
        if command=='capacity':
            actual=capacity(snapshot,[case['args']['size']])['cluster'][0]['capacity']
            equal=actual==case['capacity']
        elif command=='can-create':
            result=create(snapshot,**case['args'])
            equal=result['verdict']==case['verdict']
        elif command=='can-upscale':
            result=upscale(snapshot,**case['args'])
            expected={'2':{'feasible'},'1':{'feasible','feasible-in-steps'},'0':{'infeasible'}}[str(case['poc_score'])]
            equal=result['verdict'] in expected
        else:
            options=Namespace(scope='node',node=None,db=None,rack=None,shard_size_min=2**30,shard_size_max=25*2**30,
                              shard_used_max=25*2**30,level=1,need=None,reserve_shard_size=None,explain=False)
            for key,value in case['args'].items():setattr(options,key,value)
            result=optimize(snapshot,options)
            moves=[[s['shard_uid'],s['from_node'],s['to_node']] for s in result['plan']]
            equal=moves==case['moves']
            own={s['uid']:s['role'] for s in snapshot['shards']}
            assert all(own[s['shard_uid']]=='replica' for s in result['plan'])
        if command!='capacity':
            verify(snapshot,result['plan'],result.get('goal') if result['verdict'] in ('feasible','feasible-in-steps','goal-met') else None)
        if not equal:
            assert case.get('divergence_reason') in ALLOWED,case
            assert case.get('divergence_evidence'),case
        else:
            assert not case.get('divergence_reason'),case
    assert counts=={'capacity':3,'can-create':4,'can-upscale':4,'optimize':5}


def test_req12_no_redis_runtime():
    """Given: the v2 tree after P-1 passes
    When: running `grep -rE "redis-cli|EVAL|flushdb" src/`
    Then: there are no matches.
    """
    for path in (ROOT/'src').rglob('*.py'):
        assert re.search(r'redis-cli|EVAL|flushdb',path.read_text()) is None,path
