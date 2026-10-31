"""REQ-02 offline HTTP acceptance scenarios."""
from copy import deepcopy
import json
from pathlib import Path
import httpx
import pytest
import respx
from recap.cli import main

FIXTURE = Path(__file__).parent / 'fixtures/http/collect-8.2.json'


def recorded(monkeypatch, responses=None, status=200):
    monkeypatch.setenv('RECAP_USER', 'test-user')
    monkeypatch.setenv('RECAP_PASSWORD', 'test-password')
    data = responses or json.loads(FIXTURE.read_text())
    router = respx.mock(assert_all_called=False)
    router.start()
    for path, value in data.items():
        router.get('https://c:9443' + path).mock(return_value=httpx.Response(status, json=value))
    return router


def test_req02_complete_recorded_cluster(monkeypatch, tmp_path, capsys):
    """Given: recorded REST responses (an HTTP fixture) for a 3-node RS 8.2 cluster where all shards are visible
    When: `recap collect --url https://c:9443 --out s.json`, with credentials in env
    Then: exit 0; `s.json` validates; `provenance.partial == false`; every `shards[].used_memory` is an integer; and the test password appears neither in `s.json` nor on stderr.
    """
    from recap.snapshot import validate
    router = recorded(monkeypatch)
    try:
        target = tmp_path / 's.json'
        assert main(['collect','--url','https://c:9443','--out',str(target)]) == 0
        s = json.loads(target.read_text())
        assert validate(s) == []
        assert not s['provenance']['partial']
        assert all(type(x['used_memory']) is int for x in s['shards'])
        assert 'test-password' not in target.read_text() + capsys.readouterr().err
        assert len(router.calls) == 7
        assert all(call.request.method == 'GET' for call in router.calls)
    finally:
        router.stop()


def test_req02_partial_refused(monkeypatch, tmp_path, capsys):
    """Given: recorded responses where `/v1/shards` omits the shards of one database, as a scoped `db_viewer` would see
    When: `recap collect ...` without `--allow-partial`
    Then: exit 2; stderr names the mismatch (expected vs. visible shard count); no file is written.
    """
    data = json.loads(FIXTURE.read_text())
    data['/v1/shards'] = data['/v1/shards'][:-2]
    router = recorded(monkeypatch, data)
    try:
        target = tmp_path / 's.json'
        assert main(['collect','--url','https://c:9443','--out',str(target)]) == 2
        assert not target.exists()
        assert 'expected 6' in capsys.readouterr().err
    finally:
        router.stop()


def test_req02_flex_preserved(monkeypatch, tmp_path):
    """Given: recorded responses that include a database with `bigstore: true`
    When: `recap collect ...`
    Then: that database has `unsupported_reason == "flex"`, and its shards are present in `shards[]`.
    """
    data = json.loads(FIXTURE.read_text())
    data['/v1/bdbs'][0]['bigstore'] = True
    router = recorded(monkeypatch, data)
    try:
        target = tmp_path / 's.json'
        assert main(['collect','--url','https://c:9443','--out',str(target)]) == 0
        s = json.loads(target.read_text())
        assert s['bdbs'][0]['unsupported_reason'] == 'flex'
        assert sum(x['bdb_uid'] == 1 for x in s['shards']) == 2
    finally:
        router.stop()


def test_req02_auth_failure(monkeypatch, capsys):
    """Given: an HTTP fixture that answers 401
    When: `recap collect ...`
    Then: exit 3.
    """
    router = recorded(monkeypatch, status=401)
    try:
        assert main(['collect','--url','https://c:9443']) == 3
        captured = capsys.readouterr()
        assert 'test-password' not in captured.out + captured.err
    finally:
        router.stop()


def test_req02_partial_opt_in_and_oldest_version(monkeypatch, tmp_path):
    data = json.loads(FIXTURE.read_text())
    data['/v1/nodes'][0]['software_version'] = '7.4.0'
    data['/v1/shards'] = data['/v1/shards'][:-2]
    router = recorded(monkeypatch, data)
    try:
        target = tmp_path / 's.json'
        assert main(['collect','--url','https://c:9443','--out',str(target),'--allow-partial']) == 0
        s = json.loads(target.read_text())
        assert s['provenance']['partial']
        assert s['cluster']['rs_version'] == '7.4.0'
        assert s['cluster']['mixed_versions']
        assert s['cluster']['license'] is None
        assert len(router.calls) == 6
    finally:
        router.stop()


def test_req02_insecure_warning(monkeypatch, tmp_path, capsys):
    router = recorded(monkeypatch)
    try:
        target = tmp_path / 's.json'
        assert main(['collect','--url','https://c:9443','--out',str(target),'--insecure']) == 0
        assert 'insecure' in capsys.readouterr().err
        assert any('insecure' in w for w in json.loads(target.read_text())['provenance']['warnings'])
    finally:
        router.stop()
