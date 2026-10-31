"""REQ-10 dry-run comparison never overrides recap's own verdict."""
from datetime import datetime,timezone,timedelta
import json
from pathlib import Path
import httpx
import pytest
import respx
from recap.cli import main

FIXTURES=Path(__file__).parent/'fixtures'


def snapshot(tmp_path,version='8.2.0-78',age=0):
    s=json.loads((FIXTURES/'upscale-steps.json').read_text())
    s['cluster']['rs_version']=version
    s['collected_at']=(datetime.now(timezone.utc)-timedelta(seconds=age)).isoformat()
    path=tmp_path/'s.json';path.write_text(json.dumps(s))
    return path


def auth(monkeypatch):
    monkeypatch.setenv('RECAP_USER','test-user');monkeypatch.setenv('RECAP_PASSWORD','test-password')


def test_req10_blueprint_divergence(monkeypatch,tmp_path,capsys):
    """Given: recorded RS responses where the rebalance dry-run returns a blueprint different from the `recap` plan
    When: `recap cross-check rebalance --db 1 ...`
    Then: the output shows `placement-differs`, and the exit code equals that of `recap optimize db --db 1` on the same snapshot.
    """
    auth(monkeypatch);path=snapshot(tmp_path)
    own=main(['optimize','db','--db','1','--snapshot',str(path)]);capsys.readouterr()
    with respx.mock as router:
        router.put('https://c:9443/v1/bdbs/1/actions/rebalance?dry_run=true').mock(return_value=httpx.Response(200,json=json.loads((FIXTURES/'http/crosscheck-rebalance.json').read_text())))
        assert main(['cross-check','--snapshot',str(path),'--url','https://c:9443','rebalance','--db','1'])==own
        assert 'placement-differs' in capsys.readouterr().out
        assert all('dry_run' in str(c.request.url) for c in router.calls)


def test_req10_old_version_skips(monkeypatch,tmp_path,capsys):
    """Given: an RS 7.4 snapshot
    When: `recap cross-check can-upscale ...`
    Then: the revamp call is skipped with `requires RS >= 7.22`.
    """
    auth(monkeypatch);path=snapshot(tmp_path,'7.4')
    with respx.mock as router:
        main(['cross-check','--snapshot',str(path),'--url','https://c:9443','can-upscale','--db','1','--memory','+4GiB'])
        assert 'requires RS >= 7.22' in capsys.readouterr().out
        assert not router.calls


def test_req10_permission_denied(monkeypatch,tmp_path,capsys):
    """Given: recorded responses where `POST /v1/bdbs?dry_run` returns 403
    When: `recap cross-check can-create ...`
    Then: the comparison is skipped with `permission-denied`, and the exit code equals that of `recap can-create` with the same arguments.
    """
    auth(monkeypatch);path=snapshot(tmp_path)
    own=main(['can-create','--snapshot',str(path),'--memory','2GiB','--shards','1']);capsys.readouterr()
    with respx.mock as router:
        router.route(method='POST',path='/v1/bdbs').mock(return_value=httpx.Response(403))
        assert main(['cross-check','can-create','--snapshot',str(path),'--url','https://c:9443','--memory','2GiB','--shards','1'])==own
        assert 'permission-denied' in capsys.readouterr().out
        assert all('dry_run' in str(c.request.url) for c in router.calls)


def test_req10_stale_before_http(monkeypatch,tmp_path,capsys):
    auth(monkeypatch);path=snapshot(tmp_path,age=700)
    with respx.mock as router:
        assert main(['cross-check','--snapshot',str(path),'--url','https://c:9443','rebalance','--db','1'])==2
        assert not router.calls
        assert 'stale' in capsys.readouterr().err
