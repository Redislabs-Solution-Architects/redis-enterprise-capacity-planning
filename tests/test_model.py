"""REQ-04 model acceptance scenarios."""
import json
from pathlib import Path
import pytest

G = 2**30


def fixture():
    return json.loads((Path(__file__).parent / 'fixtures/no-rack.json').read_text())


def test_req04_slot_bound():
    """Given: a node with 100 GiB `provisional_ram`, `max_redis_servers = 10` and `shard_count = 9`
    When: `recap capacity --shard-size 5GiB`
    Then: that node's capacity is 1, with binding constraint `slots`.
    """
    from recap.model import node_capacity
    s = fixture()
    n = dict(s['nodes'][0], provisional_ram=100*G, max_redis_servers=10, shard_count=9)
    row = node_capacity(s, n, 5*G)
    assert row['capacity'] == 1 and row['binding_constraint'] == 'slots'


def test_req04_license_bound():
    """Given: license `ram_shards_limit = 20` and `ram_shards_in_use = 19`, with nodes that have RAM and slots for 10 shards
    When: `recap capacity --shard-size 1GiB`
    Then: cluster capacity is 1, with binding constraint `license`.
    """
    from recap.model import capacity
    s = fixture()
    s['cluster']['license'] = dict(ram_shards_limit=20, ram_shards_in_use=19)
    for n in s['nodes']:
        n['provisional_ram'] = 10*G
    row = capacity(s, [G])['cluster'][0]
    assert row['capacity'] == 1 and row['binding_constraint'] == 'license'


def test_req04_pre8_unknown():
    """Given: a pre-8.0 snapshot in which a node has `shard_count == max_redis_servers` and `provisional_ram == 0`
    When: `recap capacity`
    Then: that node's `free_ram` prints `unknown`, and its capacity is 0 with binding constraint `slots`.
    """
    from recap.model import node_capacity
    s = fixture()
    s['provenance']['rs_semantics']['provisional_ram'] = 'pre-8.0'
    n = dict(s['nodes'][0], provisional_ram=0, max_redis_servers=2, shard_count=2)
    row = node_capacity(s, n, G)
    assert row['free_ram'] == 'unknown'
    assert row['capacity'] == 0 and row['binding_constraint'] == 'slots'


@pytest.mark.parametrize('change,binding', [
    ({'provisional_ram':G},'ram'), ({'accept_servers':False},'node-inactive'),
    ({'status':'down'},'node-inactive'), ({'provisional_ram':10*G,'max_redis_servers':10,'shard_count':0},'none'),
])
def test_req04_binding_constraints(change,binding):
    from recap.model import node_capacity
    s = fixture()
    assert node_capacity(s, dict(s['nodes'][1], **change), G)['binding_constraint'] == binding


def test_req04_headroom_and_rack_aggregation():
    from recap.model import capacity, node_capacity
    s = fixture()
    n = dict(s['nodes'][1], total_memory=100*G, provisional_ram=10*G)
    assert node_capacity(s,n,G,0.05)['free_ram'] == 5*G
    result = capacity(s,[G])
    assert sum(row['capacity'] for row in result['racks']) == result['cluster'][0]['capacity']
