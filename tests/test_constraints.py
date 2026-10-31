"""REQ-05 shared constraint checker."""
import json
from pathlib import Path
import pytest


def fixture():
    return json.loads((Path(__file__).parent / 'fixtures/upscale-steps.json').read_text())


def test_req05_database_rack_policy():
    """Given: database A with `rack_aware == true` and database B with `rack_aware == false`
    When: `violations()` evaluates a state where each database's replica is on its master's rack (on different nodes)
    Then: exactly one violation, for A.
    """
    from recap.constraints import violations
    s=fixture()
    s['bdbs'][1]['rack_aware']=False
    s['bdbs'][2]['rack_aware']=False
    for n in s['nodes']:
        n['rack_id']='rack-a'
    errors=violations(s)
    assert len(errors)==1
    assert errors[0].bdb_uid==1 and errors[0].code=='rack-awareness'


@pytest.mark.parametrize('change,code', [
    ('ram','ram'), ('slots','slots'), ('license','license'), ('accept','accept-servers'), ('pair','anti-affinity'),
])
def test_req05_hard_constraints(change,code):
    from recap.constraints import violations
    s=fixture()
    if change=='ram': s['nodes'][0]['provisional_ram']=-1
    if change=='slots': s['nodes'][0]['max_redis_servers']=0
    if change=='license': s['cluster']['license']={'ram_shards_limit':1,'ram_shards_in_use':6}
    if change=='accept': s['nodes'][0]['accept_servers']=False
    if change=='pair':
        s['bdbs'][0]['rack_aware']=False
        s['shards'][1]['node_uid']=s['shards'][0]['node_uid']
    assert code in {e.code for e in violations(s)}


def test_req05_second_dimension_warning_only():
    from recap.constraints import violations, warnings
    s=fixture()
    s['nodes'][0]['second_rack_id']='zone-a'
    assert violations(s)==[]
    assert warnings(s)==['2d-rack-rule-unverified']
