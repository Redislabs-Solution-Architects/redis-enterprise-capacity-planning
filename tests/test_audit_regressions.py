"""Behavioral regressions reproduced by independent T13, using CLI output paths."""
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
import respx
from hypothesis import given, settings, strategies as st

from recap.cli import main

FIXTURES = Path(__file__).parent / 'fixtures'
GIB = 2**30


def invoke(argv, snapshot=None):
    out, err = io.StringIO(), io.StringIO()
    with patch('sys.stdin', io.StringIO(json.dumps(snapshot) if snapshot is not None else '')), redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


def test_req07_reserve_growth_on_each_existing_host():
    from recap.snapshot import validate
    from recap.planner.upscale import plan
    from recap.verifier import verify
    s = json.loads((FIXTURES / 'upscale-steps.json').read_text())
    s['nodes'][0]['provisional_ram'] = GIB
    s['nodes'][1]['provisional_ram'] = 4*GIB
    s['nodes'].append(dict(s['nodes'][2], uid=4, rack_id='rack-d', provisional_ram=3*GIB, shard_count=0))
    assert validate(s) == []
    code, out, err = invoke(['can-upscale', '--snapshot', '-', '--db', '1', '--memory', '+8GiB', '--format', 'json'], s)
    assert code == 0, (out, err)
    output = json.loads(out)
    assert output['verdict'] == 'feasible-in-steps'
    assert [(p['shard_uid'], p['to_node']) for p in output['plan'] if p['action']=='migrate'] == [(4,4),(6,4)]
    result = plan(s, '1', '+8GiB')
    final = verify(s, result['plan'], result['goal'])
    assert [n['provisional_ram'] for n in final['nodes']] == [0,0,10*GIB,0]
    assert [(p['uid'],p['node_uid']) for p in final['shards'] if p['bdb_uid']==1] == [(1,1),(2,2)]


def partial_collection(kind):
    responses = json.loads((FIXTURES/'http/collect-8.2.json').read_text())
    if kind == 'whole-database':
        responses['/v1/shards'] = responses['/v1/shards'][:-2]
    elif kind == 'one-copy':
        responses['/v1/shards'] = responses['/v1/shards'][:-1]
    else:
        responses['/v1/bdbs'] = responses['/v1/bdbs'][:-1]
    with patch.dict(os.environ, {'RECAP_USER':'test-user', 'RECAP_PASSWORD':'test-password'}), respx.mock(assert_all_called=False) as router:
        for path, data in responses.items():
            router.get('https://c:9443'+path).mock(return_value=httpx.Response(200,json=data))
        code, out, err = invoke(['collect','--url','https://c:9443','--allow-partial'])
    assert code == 0, err
    return json.loads(out)


@pytest.mark.parametrize('kind', ['whole-database','one-copy','invisible-database'])
def test_req02_partial_collect_compute_round_trip(kind):
    s = partial_collection(kind)
    assert s['provenance']['partial'] is True
    commands = [
        ['capacity'],
        ['can-create','--memory','2GiB','--shards','1','--replication'],
        ['can-upscale','--db','1','--memory','+4GiB'],
        ['can-upscale','--all'],
        ['optimize','node','--node','1'],
        ['report'],
    ]
    for command in commands:
        code, out, err = invoke([*command,'--snapshot','-','--allow-partial','--format','json'], s)
        assert code in (0,1), (kind, command, code, err)
        assert json.loads(out)['partial'] is True
        refused = invoke([*command,'--snapshot','-','--format','json'], s)
        assert refused[0] == 2


def test_req03_partial_opt_in_does_not_hide_invalid_references_or_duplicates():
    s = partial_collection('whole-database')
    invalid = deepcopy(s); invalid['shards'][0]['node_uid'] = 999
    assert invoke(['capacity','--snapshot','-','--allow-partial'],invalid)[0] == 2
    invalid = deepcopy(s); invalid['shards'][1]['role'] = 'master'
    assert invoke(['capacity','--snapshot','-','--allow-partial'],invalid)[0] == 2
    complete = deepcopy(s); complete['provenance']['partial'] = False
    assert invoke(['capacity','--snapshot','-','--allow-partial'],complete)[0] == 2


def test_req07_partial_target_with_missing_copies_is_conservative():
    s = partial_collection('whole-database')
    code, out, err = invoke(['can-upscale','--snapshot','-','--allow-partial','--db','3','--memory','+4GiB','--format','json'], s)
    assert code == 1, err
    assert any('partial' in reason and 'placement' in reason for reason in json.loads(out)['reasons'])


@pytest.mark.parametrize('pair_count',[1,2])
def test_req07_partial_target_requires_complete_pairs_for_each_range(pair_count):
    from recap.snapshot import validate
    s=partial_collection('whole-database')
    if pair_count==1:
        s['shards'][0]['slots']='0-8191'
        s['shards'][1]['slots']='8192-16383'
    else:
        s['bdbs'][0].update(shards_count=2,memory_size=4*GIB,sharding=True)
        s['shards'][0]['slots']=s['shards'][1]['slots']='0-8191'
        s['shards'] += [dict(s['shards'][0],uid=7,slots='8192-12287'),
                        dict(s['shards'][1],uid=8,slots='12288-16383')]
        for node in s['nodes']:node['provisional_ram']=10*GIB
    assert validate(s,allow_partial=True)==[]
    code,out,err=invoke(['can-upscale','--snapshot','-','--allow-partial','--db','1','--memory','+2GiB','--format','json'],s)
    assert code==1,err
    output=json.loads(out)
    assert output['partial'] is True
    assert output['verdict']=='infeasible'
    assert any('partial' in reason and 'placement' in reason for reason in output['reasons'])


@pytest.mark.parametrize('flags,cluster,expected', [
    (['--rack-aware','--placement','dense'], {'rack_aware':False,'default_shards_placement':'sparse'}, (True,'dense')),
    (['--no-rack-aware','--placement','sparse'], {'rack_aware':True,'default_shards_placement':'dense'}, (False,'sparse')),
    ([], {'rack_aware':False,'default_shards_placement':'dense'}, (False,'dense')),
])
def test_req10_dry_run_receives_effective_create_options(flags,cluster,expected):
    s = json.loads((FIXTURES/'no-rack.json').read_text())
    s['cluster'].update(cluster)
    s['collected_at'] = datetime.now(timezone.utc).isoformat()
    with patch.dict(os.environ, {'RECAP_USER':'test-user','RECAP_PASSWORD':'test-password'}), respx.mock as router:
        router.route(method='POST',path='/v1/bdbs').mock(return_value=httpx.Response(200,json={}))
        code, out, err = invoke(['cross-check','--snapshot','-','--url','https://c:9443','can-create','--memory','2GiB','--shards','1','--replication',*flags], s)
        assert code in (0,1), err
        body = json.loads(router.calls[0].request.content)
    assert (body.get('rack_aware'),body.get('shards_placement')) == expected


@pytest.mark.parametrize('name,command,code', [
    ('no-rack', ['can-create','--memory','2GiB','--shards','1','--replication'], 0),
    ('no-rack', ['can-create','--memory','1TiB','--shards','2','--replication'], 1),
    ('no-rack', ['can-upscale','--db','1','--memory','+1GiB'], 0),
    ('no-rack', ['can-upscale','--db','1','--memory','+1TiB'], 1),
    ('upscale-steps', ['can-upscale','--db','1','--memory','+4GiB'], 0),
    ('densify', ['optimize','cluster'], 0),
    ('no-rack', ['optimize','node','--node','1'], 0),
    ('no-rack', ['optimize','node','--node','1','--need','2GiB'], 1),
])
def test_req01_feature_cli_exit_and_schema(name,command,code):
    from jsonschema import Draft202012Validator
    s=json.loads((FIXTURES/f'{name}.json').read_text())
    actual,out,err=invoke([*command,'--snapshot','-','--format','json'],s)
    assert actual==code,(out,err)
    output=json.loads(out)
    schema=json.loads((FIXTURES.parents[1]/'src/recap/schemas/output.v1.json').read_text())
    Draft202012Validator(schema).validate(output)
    assert not output['partial']
    assert actual==0 or output['reasons']


def test_req07_unsupported_cli_exit():
    s=json.loads((FIXTURES/'no-rack.json').read_text())
    s['bdbs'][0]['unsupported_reason']='flex'
    code,out,err=invoke(['can-upscale','--snapshot','-','--db','1','--memory','20GiB'],s)
    assert code==4 and 'unsupported: flex' in err
    assert not out


@st.composite
def optimizer_topologies(draw):
    count=draw(st.integers(3,6))
    pair_count=draw(st.integers(1,5))
    s=json.loads((FIXTURES/'no-rack.json').read_text())
    template=s['nodes'][0]
    s['nodes']=[dict(template,uid=i,rack_id=f'rack-{i}',shard_count=0,
                     provisional_ram=draw(st.integers(0,15))*GIB) for i in range(1,count+1)]
    s['bdbs']=[];s['shards']=[]
    for uid in range(1,pair_count+1):
        master=draw(st.integers(1,count))
        replica=draw(st.sampled_from([n for n in range(1,count+1) if n!=master]))
        size=draw(st.sampled_from([1,2,4]))*GIB
        s['bdbs'].append(dict(uid=uid,name=f'db-{uid}',memory_size=2*size,shards_count=1,
                             replication=True,rack_aware=draw(st.booleans()),sharding=False,
                             shard_key_regex=[],shards_placement='sparse',bigstore=False,crdt=False,unsupported_reason=None))
        for node,role in ((master,'master'),(replica,'replica')):
            s['shards'].append(dict(uid=len(s['shards'])+1,bdb_uid=uid,node_uid=node,role=role,
                                    slots='0-16383',used_memory=draw(st.integers(0,1024))*2**20))
            s['nodes'][node-1]['shard_count']+=1
    for n in s['nodes']:
        n['max_redis_servers']=n['shard_count']+draw(st.integers(0,4))
    return s,draw(st.integers(1,count)),draw(st.sampled_from([1,2]))


@given(optimizer_topologies())
@settings(max_examples=40,deadline=None)
def test_req05_property_optimization_across_generated_topologies(case):
    from argparse import Namespace
    from recap.constraints import violations
    from recap.planner.optimize import plan
    from recap.verifier import verify
    s,node,level=case
    assert violations(s)==[]
    options=Namespace(scope='node',node=str(node),db=None,rack=None,shard_size_min=None,
                      shard_size_max=None,shard_used_max=False,level=level,need=None,
                      reserve_shard_size=None,explain=False)
    result=plan(s,options)
    final=verify(s,result['plan'],result.get('goal') if result['verdict']=='goal-met' else None)
    assert violations(final)==[]
