"""REQ-11 self-contained offline capacity report."""
from recap.constraints import warnings
from recap.model import capacity
from recap.planner.create import plan as create
from recap.planner.upscale import all_databases, DEFAULT_LADDER
from recap.units import parse, format_gib
from recap.verifier import verify


def build(snapshot,ladder=None):
    creates=[]
    for rung in (ladder or DEFAULT_LADDER).split(','):
        size,count=rung.rsplit(':',1)
        result=create(snapshot,parse(size),int(count),replication=True)
        verify(snapshot,result['plan'],result.get('goal') if result['verdict']=='feasible' else None)
        creates.append(dict(memory_size=parse(size),shards=int(count),verdict=result['verdict'],reasons=result['reasons']))
    upscales=all_databases(snapshot,ladder)
    for result in upscales['results']:
        verify(snapshot,result['plan'],result.get('goal') if result['verdict']!='infeasible' else None)
    cluster=snapshot['cluster']
    return dict(cluster_summary=dict(rs_version=cluster['rs_version'],mixed_versions=cluster['mixed_versions'],
                                      nodes=len(snapshot['nodes']),racks=len({n['rack_id'] for n in snapshot['nodes']}),license=cluster['license']),
                capacity=capacity(snapshot),can_create=creates,can_upscale=upscales['rows'],
                unsupported=[dict(uid=d['uid'],name=d['name'],reason=d['unsupported_reason']) for d in snapshot['bdbs'] if d['unsupported_reason']],
                warnings=list(dict.fromkeys(snapshot['provenance']['warnings']+warnings(snapshot))))


def markdown(snapshot,data):
    def cell(value):
        return str(value).replace('|','\\|').replace('\n',' ')

    def table(headers,rows):
        return ['| '+' | '.join(map(cell,headers))+' |','| '+' | '.join('---' for _ in headers)+' |']+['| '+' | '.join(map(cell,row))+' |' for row in rows]

    summary=data['cluster_summary']
    lines=['# recap capacity report','',f"Cluster: {snapshot['cluster']['name']}",
           f"RS: {summary['rs_version']}; mixed versions: {str(summary['mixed_versions']).lower()}",
           f"Nodes: {summary['nodes']}; racks: {summary['racks']}"]
    license=summary['license']
    lines.append(f"License RAM shards: {license['ram_shards_in_use']}/{license['ram_shards_limit']}" if license else 'License RAM shards: unknown')
    lines+=['','## Nodes','']
    rows=[]
    for node in snapshot['nodes']:
        capacities=[r for r in data['capacity']['nodes'] if r['uid']==node['uid']]
        first=capacities[0] if capacities else dict(free_ram=node['provisional_ram'],free_slots=node['max_redis_servers']-node['shard_count'])
        ram=format_gib(first['free_ram']) if isinstance(first['free_ram'],int) else first['free_ram']
        values='; '.join(f"{format_gib(r['shard_size'])}: {r['capacity']} ({r['binding_constraint']})" for r in capacities)
        rows.append([f"node:{node['uid']}",node['rack_id'] or 'none',ram,first['free_slots'],values])
    lines+=table(['Node','Rack','Free RAM','Free slots','Capacity by shard size'],rows)
    lines+=['','## Racks','']
    rows=[]
    for rack in sorted({n['rack_id'] for n in snapshot['nodes']},key=lambda r:r or ''):
        capacities=[r for r in data['capacity']['racks'] if r['rack_id']==rack]
        rows.append([f"rack:{rack or 'none'}",'; '.join(f"{format_gib(r['shard_size'])}: {r['capacity']} ({r['binding_constraint']})" for r in capacities)])
    lines+=table(['Rack','Capacity by shard size'],rows)
    lines+=['','## Cluster capacity','']
    lines+=table(['Shard size','Capacity','Binding constraint'],[[format_gib(r['shard_size']),r['capacity'],r['binding_constraint']] for r in data['capacity']['cluster']])
    lines+=['','## Can-create ladder (replicated)','']
    lines+=table(['Target','Shards','Verdict','Reasons'],[[f"create:{format_gib(r['memory_size'])}",r['shards'],r['verdict'],'; '.join(r['reasons'])] for r in data['can_create']])
    lines+=['','## Can-upscale ladder','']
    lines+=table(['Database','Target','Shards','Verdict','Reasons'],[[r['db_uid'],format_gib(r['target_memory']),r['target_shards'],r['verdict'],'; '.join(r['reasons'])] for r in data['can_upscale']])
    lines+=['','## Unsupported databases','']
    lines+=['- '+f"{d['uid']} ({d['name']}): {d['reason']}" for d in data['unsupported']] or ['None.']
    lines+=['','## Provenance warnings','']
    lines+=['- '+w for w in data['warnings']] or ['None.']
    return '\n'.join(lines)+'\n'
