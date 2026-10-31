"""REQ-07 upscale and exported call-order acceptance."""
import json
from pathlib import Path
import pytest

G=2**30


def fixture(name='upscale-steps'):
    return json.loads((Path(__file__).parent/f'fixtures/{name}.json').read_text())


def test_req07_memory_only_direct():
    """Given: a replicated database with 1 shard per node, where each node has 6 GiB `free_ram`
    When: `recap can-upscale --db 1 --memory +10GiB` (+5 GiB per shard)
    Then: exit 0, verdict `feasible`.
    """
    from recap.planner.upscale import plan
    s=fixture('no-rack')
    for n in s['nodes']: n['provisional_ram']=6*G
    assert plan(s,'1','+10GiB')['verdict']=='feasible'


def test_req07_sum_growth_per_node():
    """Given: a database with 2 shards on one node, each growing by 4 GiB, on a node with 6 GiB `free_ram`
    When: `recap can-upscale --db 1 --memory +16GiB` (+4 GiB per shard over 4 shards)
    Then: exit 1, verdict `infeasible`, reason `ram` on that node. The POC answers "yes" (F-14).
    """
    from recap.planner.upscale import plan
    s=fixture('no-rack');s['bdbs'][0].update(memory_size=4*G,shards_count=2,sharding=True)
    s['shards']=[dict(s['shards'][0],uid=i+1,node_uid=1 if i%2==0 else 3,role='master' if i%2==0 else 'replica',slots='0-8191' if i<2 else '8192-16383') for i in range(4)]
    for n in s['nodes']: n.update(provisional_ram=6*G,shard_count=sum(x['node_uid']==n['uid'] for x in s['shards']))
    result=plan(s,'1','+16GiB')
    assert result['verdict']=='infeasible'
    assert any(r.startswith('ram') and '1' in r for r in result['reasons'])


def test_req07_optimize_before_update():
    """Given: `tests/fixtures/upscale-steps.json`, where database 1's master node lacks 2 GiB but a 1 GiB and a 2 GiB replica of database 2 on it can move to a node with room
    When: `recap can-upscale --db 1 --memory +4GiB --format json`
    Then: exit 0, verdict `feasible-in-steps`, `plan[0].action == "migrate"`, the last step is the RS update, and the rendered text contains neither `admin@admin.com` nor `dev-pierre-lab`.

    Owner correction: the two replicas belong to databases 2 and 3.
    """
    from recap.planner.upscale import plan
    from recap.verifier import verify
    result=plan(fixture(),'1','+4GiB')
    assert result['verdict']=='feasible-in-steps'
    assert result['plan'][0]['action']=='migrate'
    assert result['plan'][-1]['action']=='rs-update'
    text='\n'.join(result['details']['rendered'])
    assert '$RECAP_USER:$RECAP_PASSWORD' in text
    assert '{url}' in text
    verify(fixture(),result['plan'],result['goal'])


def test_req07_flex_unsupported():
    """Given: a database with `unsupported_reason == "flex"`
    When: `recap can-upscale --db <it> --memory 20GiB`
    Then: exit 4, with `unsupported: flex`.
    """
    from recap.planner.upscale import plan, UnsupportedError
    s=fixture();s['bdbs'][0]['unsupported_reason']='flex'
    with pytest.raises(UnsupportedError,match='unsupported: flex'):plan(s,'1','20GiB')


def test_req07_reshard_call_order_and_regex():
    from recap.planner.upscale import plan
    from recap.verifier import verify
    s=fixture('no-rack')
    for n in s['nodes']: n.update(provisional_ram=30*G)
    result=plan(s,'1','20GiB',shards=2)
    assert result['verdict']=='feasible'
    first,last=result['plan']
    assert first['changes']['shards_count']==2
    assert first['changes']['sharding'] is True
    assert first['changes']['shard_key_regex']==['.*\\{(?<tag>.*)\\}.*','(?<tag>.*)']
    assert first['conditional']=='rs-placement'
    assert last['changes']=={'memory_size':20*G}
    verify(s,result['plan'],result['goal'])


def test_req07_ladder_keeps_current_shards():
    from recap.planner.upscale import all_databases
    s=fixture('no-rack');s['bdbs'][0]['memory_size']=12*G
    result=all_databases(s,'10GiB:1,50GiB:1')
    assert result['rows'][0]['target_memory']==50*G
