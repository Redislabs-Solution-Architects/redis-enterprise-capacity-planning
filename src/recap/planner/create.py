"""REQ-06 deterministic concrete placement with backtracking."""
from collections import defaultdict
from copy import deepcopy
from recap.constraints import violations
from recap.model import node_capacity, free_ram, shard_size


def plan(snapshot,memory,shards,replication=False,rack_aware=None,placement=None):
    if memory<=0 or shards<=0:
        raise ValueError('memory and shards must be positive')
    state=deepcopy(snapshot)
    rack_aware=snapshot['cluster']['rack_aware'] if rack_aware is None else rack_aware
    placement=placement or snapshot['cluster']['default_shards_placement']
    db=dict(uid=max([d['uid'] for d in state['bdbs']]+[s['bdb_uid'] for s in state['shards']]+[0])+1,name='new-database',memory_size=memory,
            shards_count=shards,replication=replication,rack_aware=rack_aware,sharding=shards>1,
            shard_key_regex=[],shards_placement=placement,bigstore=False,crdt=False,unsupported_reason=None)
    size=shard_size(db)
    count=shards*(2 if replication else 1)
    rows=[node_capacity(state,n,size) for n in state['nodes']]
    ram=sum(free_ram(state,n) for n in state['nodes'] if free_ram(state,n)!='unknown')
    license=state['cluster']['license']
    reason=None
    if license and license['ram_shards_limit']-license['ram_shards_in_use']<count:
        reason='license: insufficient RAM shards'
    elif ram<memory:
        reason='ram: insufficient free RAM'
    elif sum(max(0,n['max_redis_servers']-n['shard_count']) for n in state['nodes'])<count:
        reason='slots: insufficient shard slots'
    elif replication:
        caps=defaultdict(int)
        for row in rows:
            caps[row['rack_id'] if rack_aware else row['uid']]+=row['capacity']
        if sum(min(c,shards) for c in caps.values())<count:
            reason=('rack-awareness' if rack_aware else 'anti-affinity')+': insufficient independent capacity'
    if reason:
        return dict(verdict='infeasible',reasons=[reason]+(['optimize may help'] if ram>=memory else []),plan=[])
    state['bdbs'].append(db)
    start_uid=max([s['uid'] for s in state['shards']]+[0])+1
    steps=[]
    failed=[]

    def search(index):
        if index==count:
            return True
        pair=index//2 if replication else index
        slot_start=pair*16384//shards
        slot_end=(pair+1)*16384//shards-1
        role='replica' if replication and index%2 else 'master'
        shard=dict(uid=start_uid+index,bdb_uid=db['uid'],node_uid=0,role=role,slots=f'{slot_start}-{slot_end}',used_memory=0)
        candidates=sorted(state['nodes'],key=lambda n: ((n['provisional_ram'] if placement=='dense' else -n['provisional_ram']),n['uid']))
        for node in candidates:
            if node_capacity(state,node,size)['capacity']<1:
                continue
            shard['node_uid']=node['uid']
            state['shards'].append(dict(shard));node['provisional_ram']-=size;node['shard_count']+=1
            if license: license['ram_shards_in_use']+=1
            errors=violations(state)
            if not errors:
                steps.append(dict(step=index+1,action='place',shard=dict(shard)))
                if search(index+1): return True
                steps.pop()
            else:
                failed.extend(str(e) for e in errors)
            if license: license['ram_shards_in_use']-=1
            state['shards'].pop();node['provisional_ram']+=size;node['shard_count']-=1
        return False

    if search(0):
        return dict(verdict='feasible',reasons=[],plan=steps,goal=dict(kind='create',database=db),
                    details={'placement':[step['shard'] for step in steps]})
    reasons=list(dict.fromkeys(failed)) or ['ram: capacity is fragmented or nodes do not accept shards']
    if ram>=memory: reasons.append('optimize may help')
    return dict(verdict='infeasible',reasons=reasons,plan=[])
