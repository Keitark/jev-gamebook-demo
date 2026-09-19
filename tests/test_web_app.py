from pathlib import Path
import json
import sys
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from demo_book import make_demo
from gamebook_jev import Controller, Decision, GamebookEnv, ProjectAonBook
from web_app import AppError, GamebookService, LocalServer, MAX_STEPS


@pytest.fixture
def service(tmp_path, monkeypatch):
    for key in ('JEV_API_KEY', 'TYPESAFE_API_KEY', 'OPENROUTER_API_KEY'):
        monkeypatch.delenv(key, raising=False)
    return GamebookService(tmp_path)


def advance(service, state, choice='c0', backend='random'):
    data = {'revision':state['revision'], 'backend':backend}
    if choice is not None:
        data['choice'] = choice
    return service.step(state['run_id'], data)


def test_original_book_and_real_manual_victory(service):
    state = service.new_run({})
    assert state['title'] == 'The Ashen Gate'
    for _ in range(4):
        state = advance(service, state)
    assert state['path'] == ['1', '7', '9', '8', '12']
    assert state['status'] == 'success'
    assert state['steps'] == 4
    assert state['last_decision']['confidence'] is None
    assert state['last_decision']['probabilities'] == {}
    with pytest.raises(AppError, match='ended'):
        advance(service, state)


def test_death_stops_calls(service):
    state = advance(service, service.new_run({}), 'c2')
    state = advance(service, state, 'c1')
    assert state['status'] == 'deadend'
    assert 'Your journey ends' in state['section']['text']
    with pytest.raises(AppError):
        advance(service, state, None)


def test_seed_reproducibility_and_isolation(service):
    a, b = service.new_run({'seed':123}), service.new_run({'seed':123})
    assert a['run_id'] != b['run_id']
    a = advance(service, a, None)
    assert service.get_run(b['run_id']).current == '1'
    b = advance(service, b, None)
    assert a['path'] == b['path']
    assert a['last_decision']['source'] == 'random'
    assert sum(a['last_decision']['probabilities'].values()) == pytest.approx(1)


def test_optimistic_revision_guards_duplicate_calls(service):
    old = service.new_run({})
    advance(service, old)
    with pytest.raises(AppError, match='Stale') as error:
        advance(service, old)
    assert error.value.status == 409
    assert len(service.get_run(old['run_id']).trace) == 1


def test_concurrent_call_guard(service):
    state = service.new_run({})
    run = service.get_run(state['run_id'])
    with run.lock:
        with pytest.raises(AppError, match='already') as error:
            advance(service, state)
    assert error.value.status == 409


@pytest.mark.parametrize('data', [ {'book':'../secret'}, {'seed':True}, {'seed':-1}, {'seed':2**32}, {'profile':[]}, {'profile':'x'*8001} ])
def test_new_run_validation(service, data):
    with pytest.raises(AppError):
        service.new_run(data)


def test_unknown_choice_backend_and_boolean_revision(service):
    state = service.new_run({})
    for body in [ {'choice':'c99'}, {'backend':'fake'}, {'revision':False} ]:
        with pytest.raises(AppError):
            service.step(state['run_id'], {'revision':0, **body})
    assert service.get_run(state['run_id']).current == '1'


def test_no_silent_random_fallback_when_key_missing(service):
    state = service.new_run({})
    with pytest.raises(AppError, match='JEV_API_KEY'):
        advance(service, state, None, 'jev')
    assert service.get_run(state['run_id']).current == '1'
    # Manual choices do not need the selected model's key.
    state = advance(service, state, 'c0', 'jev')
    assert state['current'] == '7'
    assert state['last_decision']['source'] == 'manual'


def test_key_presence_only_and_export_no_secret(service, monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'secret-for-test-do-not-export')
    status = service.status()
    assert status['keys']['openrouter'] is True
    assert 'secret-for-test' not in json.dumps(status)
    state = service.new_run({'profile':'private profile'})
    exported = service.export(state['run_id'])
    assert 'private profile' not in json.dumps(exported)
    assert 'secret-for-test' not in json.dumps(exported)
    assert exported['mode'] == 'navigation_only'


def test_forced_transition_does_not_claim_model_confidence(service):
    state = service.new_run({})
    run = service.get_run(state['run_id'])
    run.book.sections['1'].choices = run.book.sections['1'].choices[:1]
    state = advance(service, state, None, 'jev')
    assert state['last_decision']['source'] == 'forced'
    assert state['last_decision']['confidence'] is None


def test_actual_controller_adapter_called_with_observed_history(service, monkeypatch):
    monkeypatch.setenv('JEV_API_KEY', 'stub-key')
    seen = []
    def choose(self, state, choices):
        seen.append(state)
        return Decision('c0', .8, {c.key: 1/len(choices) for c in choices}, 12.3)
    monkeypatch.setattr('web_app.JevController.choose', choose)
    state = advance(service, service.new_run({}), None, 'jev')
    assert state['last_decision']['source'] == 'jev'
    assert state['last_decision']['latency_ms'] == 12.3
    # No unseen section text or privileged goal section number in model state.
    assert 'BOOK: The Ashen Gate' in seen[0]
    assert 'The door opens on a courtyard' not in seen[0]
    assert 'ending section 12' not in seen[0]


@pytest.mark.parametrize('probabilities', [{'c0':.5}, {'c0':-1,'c1':1,'c2':1}, {'c0':float('nan'),'c1':0,'c2':0}])
def test_invalid_distributions_never_mutate_run(service, monkeypatch, probabilities):
    monkeypatch.setenv('JEV_API_KEY', 'stub-key')
    monkeypatch.setattr('web_app.JevController.choose', lambda *args: Decision('c0', .8, probabilities, 10))
    state = service.new_run({})
    with pytest.raises(AppError):
        advance(service, state, None, 'jev')
    assert service.get_run(state['run_id']).revision == 0


def test_provider_error_does_not_expose_response_or_key(service, monkeypatch):
    monkeypatch.setenv('JEV_API_KEY', 'secret-key')
    def fail(*args):
        response = requests.Response();response.status_code = 401
        raise requests.HTTPError('Authorization: Bearer secret-key', response=response)
    monkeypatch.setattr('web_app.JevController.choose', fail)
    state = service.new_run({})
    with pytest.raises(AppError) as error:
        advance(service, state, None, 'jev')
    assert 'secret-key' not in str(error.value)
    assert '401' in str(error.value)
    assert service.get_run(state['run_id']).revision == 0


def test_aon_download_is_opt_in(service):
    with pytest.raises(AppError, match='license'):
        service.download_aon({})
    with pytest.raises(AppError, match='not installed'):
        service.new_run({'book':'aon'})


def test_max_steps_and_loop_limits(service):
    state = service.new_run({});run=service.get_run(state['run_id'])
    run.trace=[{}]*MAX_STEPS
    assert run.status == 'max_steps'
    run.trace=[];run.path=['1']*6
    assert run.status == 'loop'


def test_cli_step_budget_no_extra_calls():
    class First(Controller):
        calls=0
        def choose(self,state,choices):
            self.calls+=1
            return Decision(choices[0].key, .9, {}, 0)
    for max_steps in [0,1,2]:
        controller=First(); env=GamebookEnv(make_demo(),goal='12')
        result=env.run(controller,max_steps=max_steps)
        assert len(result.trace) == result.steps == controller.calls == max_steps
        assert len(result.path) == max_steps+1
        assert result.status == 'max_steps'


def test_deadend_text_survives_parser():
    book=ProjectAonBook.from_file(Path(__file__).with_name('fixture.xml'))
    assert 'You are dead.' in book.sections['3'].text


@pytest.fixture
def http_server(service):
    server=LocalServer(0,service)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    yield server
    server.shutdown();server.server_close();thread.join(timeout=2)


def request(server,path='/',data=None,headers=None):
    headers=headers or {}
    body=json.dumps(data).encode() if data is not None else None
    req=Request(f'http://127.0.0.1:{server.server_port}'+path,data=body,headers=headers)
    try:
        with urlopen(req,timeout=3) as response:
            return response.status,response.read(),dict(response.headers)
    except HTTPError as response:
        return response.code,response.read(),dict(response.headers)


def test_http_static_keys_and_path_traversal(http_server):
    code,body,headers=request(http_server)
    assert code == 200 and b'The Decision Library' in body
    assert headers['X-Content-Type-Options']=='nosniff'
    assert 'frame-ancestors' in headers['Content-Security-Policy']
    for path in ['/.env','/static/../.env','/static/%2e%2e/web_app.py','/web_app.py']:
        assert request(http_server,path)[0] == 404
    assert request(http_server,'/static/app.js')[0] == 200


def test_http_cross_origin_and_csrf_guards(http_server):
    assert request(http_server,'/api/status',headers={'Host':'evil.test'})[0] == 403
    assert request(http_server,'/api/status',headers={'Origin':'https://evil.test'})[0] == 403
    assert request(http_server,'/api/status',headers={'Sec-Fetch-Site':'cross-site'})[0] == 403
    assert request(http_server,'/api/runs',data={},headers={'Content-Type':'application/json'})[0] == 403
    headers={'Content-Type':'application/json','X-Gamebook-Token':http_server.service.csrf}
    code,body,_=request(http_server,'/api/runs',data={},headers=headers)
    assert code == 200
    run=json.loads(body)
    code,body,_=request(http_server,f'/api/runs/{run["run_id"]}/step',data={'revision':0,'choice':'c0'},headers=headers)
    assert code == 200 and json.loads(body)['current']=='7'


def test_http_json_array_rejected(http_server):
    headers={'Content-Type':'application/json','X-Gamebook-Token':http_server.service.csrf}
    assert request(http_server,'/api/runs',data=[],headers=headers)[0]==400
