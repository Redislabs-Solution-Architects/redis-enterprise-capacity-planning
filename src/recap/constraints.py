"""REQ-05: the single placement-constraint authority."""
from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True)
class Violation:
    code: str
    message: str
    bdb_uid: int | None = None
    node_uid: int | None = None

    def __str__(self):
        return f'{self.code}: {self.message}'


def warnings(state):
    return ['2d-rack-rule-unverified'] if any(n.get('second_rack_id') is not None for n in state['nodes']) else []


def violations(state):
    errors=[]
    nodes={n['uid']:n for n in state['nodes']}
    dbs={db['uid']:db for db in state['bdbs']}
    by_node=defaultdict(list)
    pairs=defaultdict(list)
    for s in state['shards']:
        by_node[s['node_uid']].append(s)
        pairs[s['bdb_uid'],s['slots']].append(s)
    for n in nodes.values():
        if n['provisional_ram']<0:
            errors.append(Violation('ram',f"node {n['uid']} over capacity",node_uid=n['uid']))
        if n['max_redis_servers']-n['shard_count']<0:
            errors.append(Violation('slots',f"node {n['uid']} over shard limit",node_uid=n['uid']))
        if not n['accept_servers'] and by_node[n['uid']]:
            errors.append(Violation('accept-servers',f"node {n['uid']} does not accept shards",node_uid=n['uid']))
    license=state['cluster']['license']
    if license and license['ram_shards_in_use']>license['ram_shards_limit']:
        errors.append(Violation('license','RAM shard limit exceeded'))
    for (uid,slots),copies in pairs.items():
        db=dbs[uid]
        if not db['replication']:
            continue
        masters=[s for s in copies if s['role']=='master']
        replicas=[s for s in copies if s['role']=='replica']
        for master in masters:
            for replica in replicas:
                if master['node_uid']==replica['node_uid']:
                    errors.append(Violation('anti-affinity',f'database {uid} range {slots} shares a node',uid))
                elif db['rack_aware'] and nodes[master['node_uid']]['rack_id']==nodes[replica['node_uid']]['rack_id']:
                    errors.append(Violation('rack-awareness',f'database {uid} range {slots} shares a rack',uid))
    return errors
