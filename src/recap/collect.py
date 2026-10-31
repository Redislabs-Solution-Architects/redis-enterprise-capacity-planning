"""REQ-02 read-only REST collection. HTTPX client/TLS: python-httpx.org/advanced/."""
from datetime import datetime, timezone
import getpass
from importlib.resources import files
import json
import netrc
import os
from pathlib import Path
import re
import ssl
import sys
from urllib.parse import urlsplit

import httpx
from jsonschema import Draft202012Validator
from recap.snapshot import FORMAT_CHECKER


def version(value):
    return tuple(map(int, re.findall(r'\d+', value)[:3]))


def credentials(url, use_netrc=False):
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('expected an HTTPS URL without credentials')
    if use_netrc:
        auth = netrc.netrc().authenticators(parsed.hostname)
        if not auth:
            raise ValueError('no netrc credentials for this host')
        return auth[0], auth[2]
    user, password = os.getenv('RECAP_USER'), os.getenv('RECAP_PASSWORD')
    return user or input('RS user: '), password or getpass.getpass('RS password: ')


def collect(args):
    auth = credentials(args.url, args.netrc)
    verify = False if args.insecure else ssl.create_default_context(cafile=args.ca_cert) if args.ca_cert else True
    warnings = []
    if args.insecure:
        warnings.append('insecure: TLS certificate verification disabled')
        print(warnings[-1], file=sys.stderr)
    with httpx.Client(base_url=args.url, auth=auth, verify=verify, timeout=30) as client:
        def get(path):
            response = client.get(path)
            response.raise_for_status()
            return response.json()
        cluster = get('/v1/cluster')
        nodes = get('/v1/nodes')
        bdbs = get('/v1/bdbs')
        shards = get('/v1/shards')
        node_stats = {x['uid']: x for x in get('/v1/nodes/stats/last')}
        shard_stats = {x['uid']: x for x in get('/v1/shards/stats/last')}
        versions = [n['software_version'] for n in nodes]
        rs_version = min(versions, key=version)
        license = get('/v1/usage_report') if version(rs_version) >= (7,22) else None
    if license is None:
        warnings.append('license usage unknown: requires RS >= 7.22')
    output_nodes = []
    for node in nodes:
        output_nodes.append({
            **{key: node[key] for key in ('uid','total_memory','max_redis_servers','shard_count','accept_servers','status')},
            'rack_id': node.get('rack_id') or None, 'second_rack_id': node.get('second_rack_id') or None,
            'provisional_ram': node_stats[node['uid']]['provisional_memory'],
        })
    bdb_keys = ('uid','name','memory_size','shards_count','replication','rack_aware','sharding','shard_key_regex','shards_placement','bigstore','crdt')
    output_bdbs = [{**{key: db[key] for key in bdb_keys},
                   'unsupported_reason': 'flex' if db['bigstore'] else 'active-active' if db['crdt'] else None} for db in bdbs]
    output_shards = [{**{key: s[key] for key in ('uid','bdb_uid','node_uid')},
                      'role': 'replica' if s['role'] == 'slave' else s['role'],
                      'slots': s['assigned_slots'], 'used_memory': shard_stats[s['uid']]['used_memory']} for s in shards]
    partial_reasons = []
    expected = sum(n['shard_count'] for n in nodes)
    if expected != len(shards):
        partial_reasons.append(f'shard count mismatch: expected {expected}, visible {len(shards)}')
    visible_bdbs = {db['uid'] for db in bdbs}
    for s in shards:
        if s['bdb_uid'] not in visible_bdbs:
            partial_reasons.append(f"shard {s['uid']} references invisible database {s['bdb_uid']}")
    snapshot = {
        'schema_version': 1, 'collected_at': datetime.now(timezone.utc).isoformat(), 'source': 'rest',
        'cluster': {**{key: cluster[key] for key in ('name','rack_aware','default_shards_placement')},
                    **{key: value for key, value in cluster.items() if 'overbook' in key},
                    'rs_version': rs_version, 'mixed_versions': len(set(versions)) > 1,
                    'license': {key: license[key] for key in ('ram_shards_limit','ram_shards_in_use')} if license is not None else None},
        'nodes': output_nodes, 'bdbs': output_bdbs, 'shards': output_shards,
        'provenance': {'collector_user_role': None, 'partial': bool(partial_reasons),
                       'partial_reasons': partial_reasons, 'warnings': warnings,
                       'rs_semantics': {'provisional_ram': '8.0+' if version(rs_version) >= (8,0) else 'pre-8.0'}},
    }
    schema = json.loads(files('recap').joinpath('schemas/snapshot.v1.json').read_text())
    Draft202012Validator(schema, format_checker=FORMAT_CHECKER).validate(snapshot)
    if partial_reasons and not args.allow_partial:
        print('; '.join(partial_reasons) + '; use --allow-partial', file=sys.stderr)
        return 2
    serialized = json.dumps(snapshot, indent=2)
    if auth[1] and auth[1] in serialized:
        raise ValueError('collection output contains credential material')
    if args.out == '-':
        print(serialized)
    else:
        Path(args.out).write_text(serialized + '\n', encoding='utf-8')
    return 0


def run(args):
    try:
        return collect(args)
    except (httpx.HTTPError, OSError, ValueError, KeyError) as exc:
        # Never print response bodies, URLs or exception strings carrying credentials.
        print(f'collection failed: {type(exc).__name__}', file=sys.stderr)
        return 3
