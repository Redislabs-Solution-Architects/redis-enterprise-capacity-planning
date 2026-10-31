"""REQ-04 independent RAM, slot and license bounds, in integer bytes."""
from decimal import Decimal


def shard_size(db):
    copies = db['shards_count'] * (2 if db['replication'] else 1)
    size, remainder = divmod(db['memory_size'], copies)
    if remainder:
        raise ValueError('database memory_size does not yield an integer-byte shard size')
    return size


def free_ram(snapshot, node, headroom=0):
    if snapshot['provenance']['rs_semantics'].get('provisional_ram') == 'pre-8.0' and node['max_redis_servers'] == node['shard_count'] and node['provisional_ram'] == 0:
        return 'unknown'
    return max(0, node['provisional_ram'] - int(Decimal(str(headroom))*node['total_memory']))


def node_capacity(snapshot, node, size, headroom=0):
    if size <= 0:
        raise ValueError('shard size must be greater than zero')
    ram = free_ram(snapshot,node,headroom)
    slots = node['max_redis_servers'] - node['shard_count']
    memory_bound = ram // size if ram != 'unknown' else 0
    count = max(0, min(memory_bound, slots))
    if not node['accept_servers'] or node['status'] != 'active':
        count, binding = 0, 'node-inactive'
    elif ram == 'unknown' or slots < memory_bound:
        binding = 'slots'
    elif memory_bound < slots:
        binding = 'ram'
    else:
        binding = 'none'
    return dict(uid=node['uid'], rack_id=node['rack_id'], shard_size=size,
                free_ram=ram, free_slots=slots, capacity=count, binding_constraint=binding)


def capacity(snapshot, sizes=None, headroom=0):
    if not 0 <= headroom <= 1:
        raise ValueError('--ram-headroom must be between 0 and 1')
    sizes = sizes or sorted({shard_size(db) for db in snapshot['bdbs']})
    result = dict(nodes=[], racks=[], cluster=[])
    for size in sizes:
        rows = [node_capacity(snapshot,n,size,headroom) for n in snapshot['nodes']]
        result['nodes'].extend(rows)
        racks = sorted({n['rack_id'] for n in snapshot['nodes']}, key=lambda r: r or '')
        for rack in racks:
            members = [r for r in rows if r['rack_id'] == rack]
            constraints = {r['binding_constraint'] for r in members}
            result['racks'].append(dict(rack_id=rack, shard_size=size, capacity=sum(r['capacity'] for r in members),
                                        binding_constraint=next(iter(constraints)) if len(constraints)==1 else 'none'))
        count = sum(r['capacity'] for r in rows)
        license = snapshot['cluster']['license']
        remaining = max(0, license['ram_shards_limit']-license['ram_shards_in_use']) if license else count
        binding = 'license' if remaining < count else 'none'
        result['cluster'].append(dict(shard_size=size, capacity=min(count,remaining), binding_constraint=binding))
    return result
