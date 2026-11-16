"""Isolated worker: imports controller and adapter from exactly one frozen source tree."""
from __future__ import annotations
import json
from pathlib import Path
import sys
import time


def execute(config):
    sys.path.insert(0, config['source'])
    from promptboundary.core import BoundaryController, State
    from promptboundary.upstream import OpenAICompatible, StageModel, TOKEN_FIELDS, MockModel
    case, arm = config['case'], config['arm']
    mock = config.get('_wiring_mock', False)
    upstream = MockModel() if mock else OpenAICompatible(config['base_url'], config['model'])
    class Checked:
        model = upstream.model
        fixture_detected = False
        def complete(self, messages, **params):
            if self.fixture_detected:
                raise ValueError('Fixture provenance')
            r = upstream.complete(messages, **params)
            if not mock and (r.get('model') == 'promptboundary-mock' or r.get('promptboundary_usage_source') == 'mock_estimate'):
                self.fixture_detected = True
                raise ValueError('Fixture provenance')
            return r
    checked = Checked()
    generation = config['generation']
    skill = config['skill']
    prefix = skill if arm in 'BDF' else ''
    staged = StageModel(checked, generation=generation, system_prefix=prefix)
    calls = staged.calls
    history = case['history']
    visible = [] if case['evict_after_observe'] else history
    status, reply, events, attempts = 'ok', '', [], 0
    setup_calls, setup_ms = 0, 0.0
    started=time.perf_counter()
    try:
        if arm in 'CDEF':
            controller=BoundaryController(staged,max_retries=1)
            state=State()
            try:
                for index, earlier in enumerate(history):
                    if earlier['role']=='user':
                        state=controller.observe(state,earlier['content'],history[:index])
                if case['evict_after_observe']:
                    serialized=state.to_dict()
                    serialized['history']=[]
                    state=State.from_dict(serialized)
            finally:
                setup_calls=len(calls)
                setup_ms=(time.perf_counter()-started)*1000
            result=controller.run(state,case['user_text'],visible)
            status,reply,events,attempts=result.status,result.text,result.events,result.attempts
        else:
            messages=([{'role':'system','content':prefix}] if prefix else [])+visible+[{'role':'user','content':case['user_text']}]
            counts=dict.fromkeys(TOKEN_FIELDS)
            source='unavailable'
            t=time.perf_counter()
            try:
                result=checked.complete(messages,**generation)
                usage=result.get('usage') or {}
                if all(type(usage.get(k)) is int and usage[k]>=0 for k in TOKEN_FIELDS):
                    counts={k:usage[k] for k in TOKEN_FIELDS}
                    source=result.get('promptboundary_usage_source','provider')
                choice=result['choices'][0]
                reply=choice['message']['content']
                if not isinstance(reply,str):raise ValueError('Missing output')
                events=[f"finish:{choice.get('finish_reason')}"]
                attempts=1
            finally:
                calls.append(dict(stage='chat',usage_source=source,**counts,elapsed_ms=round((time.perf_counter()-t)*1000,3)))
    except Exception as exc:
        status='error'
        events.append(f'runtime:{type(exc).__name__}')
    if checked.fixture_detected:
        raise ValueError('Fixture endpoint cannot generate measured evidence')
    elapsed=(time.perf_counter()-started)*1000
    return dict(mode='mock_wiring_only' if mock else 'model',case=case['id'],arm=arm,group=case['group'],language=case['language'],evicted=case['evict_after_observe'],
        status=status,answer=reply,events=events,attempts=attempts,calls=calls,setup_calls=setup_calls,
        setup_ms=round(setup_ms,3),reply_ms=round(elapsed-setup_ms,3),elapsed_ms=round(elapsed,3),
        **{k:sum(c[k] for c in calls) if calls and all(c[k] is not None for c in calls) else None for k in TOKEN_FIELDS})

if __name__=='__main__':
    print(json.dumps(execute(json.loads(sys.stdin.read())),ensure_ascii=False))
