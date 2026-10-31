"""Self-contained visual rendering of an already calculated, verified report."""
from html import escape

from recap.model import free_ram
from recap.render import render as render_commands
from recap.units import format_gib


STYLE = """
:root{color-scheme:light dark;--bg:#fafaf9;--surface:#fff;--text:#163341;--muted:#58595b;
--line:#d9d9d9;--soft:#f3f3f3;--primary:#0060d1;--primary-bg:#eaf6ff;--success:#166534;
--success-bg:#f0fdf4;--warning:#92400e;--warning-bg:#fff8e1;--danger:#991b1b;--danger-bg:#fff1f1;
--ram:#0070f3;--slots:#15803d;--track:#e9e9e9;--focus:#0070f3;font-family:Geist,"Geist Sans",system-ui,sans-serif}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font-size:14px;line-height:1.55}
a{color:var(--primary)}a:focus-visible,summary:focus-visible{outline:2px solid var(--focus);outline-offset:4px}
main{max-width:1360px;margin:auto;padding:32px 32px 48px;min-width:0}
header{border-bottom:1px solid var(--line);padding-bottom:24px;margin-bottom:24px}
.eyebrow{font-size:12px;letter-spacing:.12em;font-weight:600;color:var(--muted);margin:0 0 8px}
h1{font-size:32px;line-height:1.2;margin:0 0 12px;letter-spacing:-.03em;overflow-wrap:anywhere}
h2{font-size:20px;margin:0 0 8px;letter-spacing:-.02em}h3{font-size:15px;margin:0 0 8px}
p{margin:8px 0}.muted,.caption{color:var(--muted)}.caption{font-size:12px;margin-top:8px}
.meta{display:flex;flex-wrap:wrap;gap:8px 20px;color:var(--muted);font-size:13px}
nav{display:flex;gap:8px;flex-wrap:wrap;margin-top:20px}nav a{padding:6px 12px;background:var(--surface);border:1px solid var(--line);border-radius:6px;text-decoration:none}
nav a:hover,nav a:active{background:var(--primary-bg);border-color:var(--primary)}
.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));background:var(--surface);border:1px solid var(--line);border-radius:8px;margin:24px 0;overflow:hidden}
.metric{padding:20px;border-right:1px solid var(--line);min-width:0}.metric:last-child{border:0}
.metric .label{font-size:12px;color:var(--muted);font-weight:500}.metric strong{display:block;font-size:26px;line-height:1.3;margin:8px 0;font-weight:600;overflow-wrap:anywhere}
.metric small{display:block;color:var(--muted);font-size:12px}
.panel{background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:24px;margin:24px 0;min-width:0;scroll-margin-top:16px}
.panel>p:first-of-type{margin-bottom:16px}.chart-grid{display:grid;grid-template-columns:1fr 1fr;gap:24px;min-width:0}
.chart{min-width:0}figure{margin:0}.bar-list{max-height:520px;overflow-y:auto;padding-right:4px}
.bar-row{display:grid;grid-template-columns:minmax(80px,1fr) minmax(80px,2fr) minmax(100px,1.5fr);gap:12px;align-items:center;margin:16px 0;font-size:12px}
.bar-row .bar-label{overflow-wrap:anywhere}.bar-row .bar-value{font-variant-numeric:tabular-nums;overflow-wrap:anywhere}
.bar-row svg{display:block;width:100%;height:24px;overflow:visible}.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
svg text{fill:var(--text);font-family:Geist,system-ui,sans-serif;font-size:13px}
svg .bar-bg{fill:var(--track)}svg .bar-ram{fill:var(--ram)}svg .bar-slots{fill:var(--slots)}
svg .bar-capacity{fill:var(--ram)}svg .bar-unknown{fill:var(--track);stroke:var(--muted);stroke-dasharray:4 3}
.legend{display:flex;gap:16px;flex-wrap:wrap;font-size:12px;color:var(--muted);margin:12px 0}
.legend span{display:inline-flex;align-items:center;gap:6px}.swatch{display:inline-block;width:10px;height:10px;border-radius:2px;background:var(--ram)}
.swatch.slots{background:var(--slots)}.swatch.track{background:var(--track)}
.table-wrap{overflow-x:auto;max-width:100%;margin-top:16px;border:1px solid var(--line);border-radius:6px}
table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:left;padding:12px 16px;border-bottom:1px solid var(--line);vertical-align:top}
th{background:var(--soft);color:var(--muted);font-size:12px;font-weight:600;white-space:nowrap}
td{overflow-wrap:anywhere}tr:last-child td{border-bottom:0}tbody tr:hover{background:var(--soft)}
.numeric{white-space:nowrap;font-variant-numeric:tabular-nums}.mono,code,pre{font-family:"Source Code Pro",ui-monospace,SFMono-Regular,Consolas,monospace}
.status{display:inline-block;border-radius:4px;padding:3px 8px;font-size:12px;font-weight:600;white-space:nowrap}
.status.success{background:var(--success-bg);color:var(--success)}.status.danger{background:var(--danger-bg);color:var(--danger)}
.status.notice{background:var(--primary-bg);color:var(--primary)}.status.neutral{background:var(--soft);color:var(--muted)}
.banner{border:1px solid var(--warning);border-radius:6px;padding:16px;background:var(--warning-bg);color:var(--warning);margin:16px 0;overflow-wrap:anywhere}
.banner strong{display:block;margin-bottom:4px}.empty{padding:20px;background:var(--soft);border-radius:6px;color:var(--muted)}
details{border:1px solid var(--line);border-radius:6px;margin-top:12px;padding:0 16px;min-width:0}
summary{padding:12px 0;cursor:pointer;font-weight:500;overflow-wrap:anywhere}summary:hover{color:var(--primary)}
details[open]>summary{border-bottom:1px solid var(--line);margin-bottom:12px}details .table-wrap{margin-bottom:16px}
pre{background:var(--soft);border:1px solid var(--line);border-radius:6px;padding:16px;overflow-wrap:anywhere;white-space:pre-wrap;font-size:12px;max-width:100%}
ul{padding-left:20px}li{margin:6px 0;overflow-wrap:anywhere}.warning-list{color:var(--warning)}
dl{display:grid;grid-template-columns:160px 1fr;gap:8px 16px;font-size:13px}dt{color:var(--muted)}dd{margin:0;overflow-wrap:anywhere}
footer{color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:20px}
@media(prefers-color-scheme: dark){:root{--bg:#07151c;--surface:#0d212c;--text:#fcfcfc;--muted:#b9c2c6;--line:#2d4754;
--soft:#163341;--primary:#8cc4fc;--primary-bg:#10243e;--success:#86efac;--success-bg:#052e16;
--warning:#fde68a;--warning-bg:#4a0d03;--danger:#fca5a5;--danger-bg:#450a0a;--ram:#52a9ff;--slots:#4ade80;--track:#2d4754;--focus:#8cc4fc}}
@media(max-width:900px){.chart-grid{grid-template-columns:1fr}.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}
.metric:nth-child(2){border-right:0}.metric:nth-child(-n+2){border-bottom:1px solid var(--line)}}
@media(max-width:540px){main{padding:20px 12px 32px}.panel{padding:16px 12px}.metric{padding:16px 12px}
h1{font-size:26px}.metric strong{font-size:22px}th,td{padding:10px}dl{grid-template-columns:1fr;gap:4px}dd{margin-bottom:12px}}
@media print{:root{color-scheme:light;--bg:#fff;--surface:#fff;--text:#163341;--muted:#58595b;--line:#bcbec0;--soft:#f3f3f3;
--primary:#0060d1;--primary-bg:#eaf6ff;--success:#166534;--success-bg:#f0fdf4;--warning:#92400e;--warning-bg:#fff8e1;
--danger:#991b1b;--danger-bg:#fff1f1;--ram:#0070f3;--slots:#15803d;--track:#e9e9e9}
body{font-size:10pt}main{max-width:none;padding:0}nav{display:none}.panel{break-inside:avoid;padding:16px;margin:16px 0}
.chart-grid{grid-template-columns:1fr}.bar-list{max-height:none;overflow:visible}.metrics{grid-template-columns:repeat(4,minmax(0,1fr))}.metric{padding:12px;border-bottom:0!important}
.table-wrap{overflow:visible}table{font-size:9pt}th,td{padding:8px}.status{white-space:normal}*{print-color-adjust:exact;-webkit-print-color-adjust:exact}}
"""


def _e(value):
    return escape(str(value), quote=True)


def _badge(verdict):
    tone={'feasible':'success','feasible-in-steps':'notice','infeasible':'danger'}.get(verdict,'neutral')
    return f'<span class="status {tone}">{_e(verdict)}</span>'


def _table(headers,rows):
    head=''.join(f'<th scope="col">{_e(h)}</th>' for h in headers)
    body=''.join('<tr>'+''.join(f'<td>{cell}</td>' for cell in row)+'</tr>' for row in rows)
    return f'<div class="table-wrap" tabindex="0" role="region" aria-label="{_e(headers[0])} table"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def _chart(title,identifier,rows,kind,description):
    if not rows:
        return '<p class="empty">No nodes or capacity rows in this snapshot.</p>'
    bars=[]
    for index,(label,value,limit,display) in enumerate(rows):
        width=0 if value is None or limit<=0 else 360*max(0,min(value/limit,1))
        bar=(f'<rect class="bar-unknown" x="0" y="6" width="360" height="12" rx="3"/>' if value is None else
             f'<rect class="bar-{kind}" x="0" y="6" width="{width:.2f}" height="12" rx="3"/>')
        label_id=f'{identifier}-{index}-title'
        bars.append(f'<div class="bar-row"><span class="bar-label">{_e(label)}</span>'
                    f'<svg viewBox="0 0 360 24" preserveAspectRatio="none" role="img" aria-labelledby="{label_id}">'
                    f'<title id="{label_id}">{_e(title)} — {_e(label)}: {_e(display)}</title>'
                    f'<rect class="bar-bg" x="0" y="6" width="360" height="12" rx="3"/>{bar}</svg>'
                    f'<span class="bar-value">{_e(display)}</span></div>')
    return f'<figure><figcaption class="sr-only">{_e(description)}</figcaption><div class="bar-list">'+''.join(bars)+'</div></figure>'


def _panel(title,identifier,body,description=''):
    return f'<section class="panel" id="{identifier}" aria-labelledby="{identifier}-heading"><h2 id="{identifier}-heading">{_e(title)}</h2>'+(
        f'<p class="muted">{_e(description)}</p>' if description else '')+body+'</section>'


def render(snapshot,data):
    """Render a verified report as one offline HTML document, without mutation."""
    cluster=snapshot['cluster']
    node_rows={r['uid']:r for r in data['capacity']['nodes']}
    ram_rows=[];slot_rows=[];table_rows=[]
    known_ram=0;unknown_nodes=0;free_slots=0
    sizes=sorted({r['shard_size'] for r in data['capacity']['nodes']})
    for node in snapshot['nodes']:
        row=node_rows.get(node['uid'])
        ram=row['free_ram'] if row else free_ram(snapshot,node)
        slots=node['max_redis_servers']-node['shard_count']
        unknown=ram=='unknown'
        if unknown:unknown_nodes+=1
        else:known_ram+=ram
        free_slots+=slots
        ram_label='unknown' if unknown else format_gib(ram)
        ram_rows.append((f"Node {node['uid']}",None if unknown else ram,node['total_memory'],f"{ram_label} / {format_gib(node['total_memory'])}"))
        slot_rows.append((f"Node {node['uid']}",slots,node['max_redis_servers'],f"{slots} free / {node['max_redis_servers']}"))
        capacities=[]
        for size in sizes:
            value=next((r for r in data['capacity']['nodes'] if r['uid']==node['uid'] and r['shard_size']==size),None)
            capacities.append(f"<span class=\"numeric\">{value['capacity']}</span><br><span class=\"caption\">{_e(value['binding_constraint'])}</span>" if value else 'unknown')
        table_rows.append([f"<span class=\"mono\">node:{node['uid']}</span>",_e(node['rack_id'] or 'No rack'),
                           _e(ram_label),_e(slots),*capacities])
    license=cluster['license']
    license_value=str(license['ram_shards_limit']-license['ram_shards_in_use']) if license else 'unknown'
    license_detail=f"{license['ram_shards_in_use']} of {license['ram_shards_limit']} RAM shards in use" if license else 'License allowance was not available'
    metrics=[('Nodes / rack groups',f"{len(snapshot['nodes'])} / {data['cluster_summary']['racks']}",'Groups with no rack ID are labeled explicitly'),
             ('Free planning RAM',format_gib(known_ram),f'{unknown_nodes} node(s) unknown; sum of known values' if unknown_nodes else 'Sum of reported free provisional RAM'),
             ('Free shard slots',str(free_slots),'Reported slot limits minus shard counts'),
             ('License headroom',license_value,license_detail)]
    metric_html='<div class="metrics">'+''.join(f'<div class="metric"><span class="label">{_e(label)}</span><strong>{_e(value)}</strong><small>{_e(note)}</small></div>' for label,value,note in metrics)+'</div>'

    partial=''
    if snapshot['provenance']['partial']:
        reasons='; '.join(snapshot['provenance']['partial_reasons']) or 'Visibility is incomplete.'
        partial=f'<aside class="banner"><strong>PARTIAL SNAPSHOT</strong>{_e(reasons)} Results reflect incomplete visibility.</aside>'
    mixed='<span class="status notice">Mixed versions</span>' if cluster['mixed_versions'] else ''
    title=_e(cluster['name'])
    header=f'<header><p class="eyebrow">RECAP / OFFLINE CAPACITY REPORT</p><h1>{title}</h1><div class="meta"><span>Snapshot: <span class="mono">{_e(snapshot["collected_at"])}</span></span><span>RS {_e(cluster["rs_version"])}</span><span>Source: {_e(snapshot["source"])}</span>{mixed}</div><nav aria-label="Report sections"><a href="#nodes">Nodes</a><a href="#racks">Racks</a><a href="#create">Can-create</a><a href="#upscale">Can-upscale</a><a href="#provenance">Provenance</a></nav></header>'

    charts='<div class="chart-grid"><div class="chart"><h3>Free planning RAM</h3>'+_chart('Free planning RAM by node','node-ram',ram_rows,'ram','Blue bars are free provisional RAM relative to physical memory; exact values are printed.')+'<p class="caption">Free provisional RAM / physical node memory. Remaining width is not a measurement of database memory used.</p></div><div class="chart"><h3>Free shard slots</h3>'+_chart('Free shard slots by node','node-slots',slot_rows,'slots','Green bars show free shard slots relative to each node limit; exact values are printed.')+'<p class="caption">Free slots / configured shard slot limit.</p></div></div>'
    node_table=_table(['Node','Rack','Free planning RAM','Free slots',*[format_gib(s)+' capacity' for s in sizes]],table_rows) if table_rows else '<p class="empty">No nodes in this snapshot.</p>'
    nodes=_panel('Node resources','nodes',charts+node_table,'Read RAM, slots and placement constraints together. A free-RAM total alone does not establish feasibility.')

    rack_html=[]
    for index,row in enumerate(data['capacity']['cluster']):
        size=row['shard_size'];racks=[r for r in data['capacity']['racks'] if r['shard_size']==size]
        maximum=max([r['capacity'] for r in racks]+[1])
        rows=[(r['rack_id'] or 'No rack',r['capacity'],maximum,f"{r['capacity']} shards") for r in racks]
        chart=_chart('Capacity by rack','rack-'+str(index),rows,'capacity','Capacity in individual shard copies for this shard size; exact counts are printed.')
        table=_table(['Rack','Individual shard capacity','Binding constraint'],[[_e(r['rack_id'] or 'No rack'),_e(r['capacity']),_e(r['binding_constraint'])] for r in racks])
        rack_html.append(f'<details{" open" if index==0 else ""}><summary>{_e(format_gib(size))} per shard · cluster limit {_e(row["capacity"])} · {_e(row["binding_constraint"])}</summary>{chart}{table}</details>')
    racks=_panel('Capacity by rack','racks',''.join(rack_html) or '<p class="empty">No database shard sizes available for capacity comparison.</p>','Capacity counts individual shard copies. The cluster limit additionally observes the known license allowance.')

    creates=_table(['Database memory','Primary shards','Verdict','Reasons'],[[_e(format_gib(r['memory_size'])),_e(r['shards']),_badge(r['verdict']),_e('; '.join(r['reasons']) or 'Placement verified')] for r in data['can_create']]) if data['can_create'] else '<p class="empty">No database creation targets.</p>'
    create_panel=_panel('Can-create','create',creates,'Replicated database targets from the configured ladder. Memory includes both primary and replica copies.')
    db_names={d['uid']:d['name'] for d in snapshot['bdbs']}
    upscale_rows=[]
    for row in data['can_upscale']:
        plan=''
        if row['plan']:
            commands='\n'.join(render_commands(row['plan']))
            plan=f'<details><summary>Inspect plan · {len(row["plan"])} steps</summary><pre>{_e(commands)}</pre><p class="caption">Exported commands for review. Re-collect and re-check before conditional updates.</p></details>'
        upscale_rows.append([f'<span class="mono">db:{row["db_uid"]}</span><br>{_e(db_names.get(row["db_uid"],"unknown"))}',_e(format_gib(row['target_memory'])),_e(row['target_shards']),_badge(row['verdict']),_e('; '.join(row['reasons']))+plan])
    upscales=_table(['Database','Target memory','Primary shards','Verdict','Reasons / verified plan'],upscale_rows) if upscale_rows else '<p class="empty">No database has an eligible next upscale rung.</p>'
    upscale_panel=_panel('Can-upscale','upscale',upscales,'Existing target shards stay in place. feasible-in-steps includes preliminary moves of other shards; commands are never executed by this report.')
    unsupported=_table(['Database','Name','Unsupported reason'],[[_e(r['uid']),_e(r['name']),_e(r['reason'])] for r in data['unsupported']]) if data['unsupported'] else '<p class="muted">No unsupported databases reported.</p>'
    unsupported_panel=_panel('Unsupported targets','unsupported',unsupported,'Reported resource use still affects capacity even when a database cannot be planned.')
    warning_html='<ul class="warning-list">'+''.join(f'<li>{_e(w)}</li>' for w in data['warnings'])+'</ul>' if data['warnings'] else '<p class="muted">No provenance warnings recorded.</p>'
    metadata=[('Collected at',snapshot['collected_at']),('Source',snapshot['source']),('Snapshot schema',snapshot['schema_version']),('Partial',str(snapshot['provenance']['partial']).lower()),('Provisional RAM semantics',snapshot['provenance']['rs_semantics'].get('provisional_ram','unknown'))]
    provenance=_panel('Provenance & limitations','provenance','<dl>'+''.join(f'<dt>{_e(k)}</dt><dd>{_e(v)}</dd>' for k,v in metadata)+'</dl>'+warning_html,
                      'This is a report of captured state, not a reservation of resources or live cluster validation. Unknown information remains unknown.')
    footer='<footer>Generated by recap · self-contained offline report · no external assets or cluster requests. Use your browser print dialog to save a PDF.</footer>'
    return '<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'"><title>recap · '+title+'</title><style>'+STYLE+'</style></head><body><main>'+header+partial+metric_html+nodes+racks+create_panel+upscale_panel+unsupported_panel+provenance+footer+'</main></body></html>\n'
