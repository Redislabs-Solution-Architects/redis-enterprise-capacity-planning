"""REQ-09 replay; independent from model and planner, sharing only constraints."""
from copy import deepcopy
from recap.constraints import violations


class VerificationError(ValueError):
    pass


def verify(snapshot, steps, goal=None):
    state=deepcopy(snapshot)
    if goal and goal.get('kind')=='create':
        state['bdbs'].append(deepcopy(goal['database']))

    def db_size(db):
        return db['memory_size']//(db['shards_count']*(2 if db['replication'] else 1))

    def allocation(shard,sign):
        node=next(n for n in state['nodes'] if n['uid']==shard['node_uid'])
        db=next(d for d in state['bdbs'] if d['uid']==shard['bdb_uid'])
        node['provisional_ram']-=sign*db_size(db)
        node['shard_count']+=sign
        if state['cluster']['license']:
            state['cluster']['license']['ram_shards_in_use']+=sign

    for k,step in enumerate(steps,1):
        try:
            action=step['action']
            if action=='migrate':
                shard=next(s for s in state['shards'] if s['uid']==step['shard_uid'])
                if shard['node_uid']!=step['from_node'] or step['from_node']==step['to_node']:
                    raise ValueError('migration source mismatch')
                allocation(shard,-1)
                shard['node_uid']=step['to_node']
                allocation(shard,1)
            elif action=='failover':
                master=next(s for s in state['shards'] if s['uid']==step['shard_uid'] and s['role']=='master')
                replica=next(s for s in state['shards'] if s['bdb_uid']==master['bdb_uid'] and s['slots']==master['slots'] and s['role']=='replica')
                master['role'],replica['role']='replica','master'
            elif action=='place':
                shard=deepcopy(step['shard'])
                if any(s['uid']==shard['uid'] for s in state['shards']):
                    raise ValueError('duplicate shard uid')
                state['shards'].append(shard)
                allocation(shard,1)
            elif action=='rs-update':
                db=next(d for d in state['bdbs'] if d['uid']==step['bdb_uid'])
                old=[s for s in state['shards'] if s['bdb_uid']==db['uid']]
                for shard in old:
                    allocation(shard,-1)
                db.update(deepcopy(step['changes']))
                if 'assumed_placement' in step:
                    state['shards']=[s for s in state['shards'] if s['bdb_uid']!=db['uid']]+deepcopy(step['assumed_placement'])
                for shard in state['shards']:
                    if shard['bdb_uid']==db['uid']:
                        allocation(shard,1)
            else:
                raise ValueError('unknown plan action')
            problems=violations(state)
            if problems:
                raise ValueError('; '.join(map(str,problems)))
        except (KeyError,StopIteration,ValueError) as exc:
            raise VerificationError(f'internal-error: plan failed verification at step {k}: {exc}') from exc
    if goal:
        kind=goal['kind']
        if kind=='beneficial':
            met=any(s['action']=='migrate' for s in steps)
        elif kind=='freed':
            nodes=set(goal['nodes'])
            before=sum(n['provisional_ram'] for n in snapshot['nodes'] if n['uid'] in nodes)
            after=sum(n['provisional_ram'] for n in state['nodes'] if n['uid'] in nodes)
            met=after-before>=goal['bytes']
        elif kind in ('create','upscale'):
            db=goal['database']
            actual=next((d for d in state['bdbs'] if d['uid']==db['uid']),None)
            met=actual is not None and all(actual[key]==db[key] for key in ('memory_size','shards_count'))
            copies=[s for s in state['shards'] if s['bdb_uid']==db['uid']]
            met=met and len(copies)==db['shards_count']*(2 if db['replication'] else 1)
            if db['replication']:
                slots={s['slots'] for s in copies}
                met=met and all(sorted(s['role'] for s in copies if s['slots']==slot)==['master','replica'] for slot in slots)
        else:
            met=False
        if not met:
            raise VerificationError(f'internal-error: plan failed verification at step {len(steps)}: goal not met')
    return state
