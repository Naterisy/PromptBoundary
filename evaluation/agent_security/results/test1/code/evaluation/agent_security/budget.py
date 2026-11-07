"""Durable, cross-process preflight reservations for a separately authorized experiment."""
from contextlib import contextmanager
from decimal import Decimal
import fcntl
import json
import os
from pathlib import Path
import uuid

RATES = {'gpt-6.1-sol': (2, .1, 2.5, 10), 'gpt-6-astra': (10, 1, 12.5, 50),
         'gpt-5.4-mini-2026-03-17': (.75, .075, .75, 4.5)}
HARD_LIMIT = Decimal('9.50')

class BudgetExceeded(RuntimeError):
    pass


def cost(model, usage):
    prices = [Decimal(str(x)) for x in RATES[model]]
    details = usage.get('input_tokens_details') or {}
    total, output = usage['input_tokens'], usage['output_tokens']
    read = details.get('cached_tokens', 0)
    write = details.get('cache_write_tokens', details.get('cache_creation_tokens', 0))
    ordinary = total-read-write
    if any(type(v) is not int or v<0 for v in (ordinary, read, write, output)):
        raise ValueError('Unsupported usage breakdown')
    return sum(Decimal(n)*r for n,r in zip((ordinary,read,write,output),prices))/1_000_000


def reservation(model, body):
    # UTF-8 bytes upper-bound ordinary byte-token counts. Include JSON schema and
    # substantial hidden framing allowance. Output cap includes reasoning tokens.
    encoded = json.dumps(body, ensure_ascii=False).encode()
    limit = body['max_output_tokens']
    if type(limit) is not int or not 1 <= limit <= 4096:
        raise ValueError('Explicit bounded output token cap required')
    inp = len(encoded) + 4096
    rates = RATES[model]
    return (Decimal(inp)*Decimal(str(max(rates[:3])))+Decimal(limit)*Decimal(str(rates[3])))/1_000_000


class Ledger:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def transaction(self):
        # A separate lock inode remains stable while the JSON is atomically replaced.
        with self.path.with_suffix('.lock').open('a+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            data = json.loads(self.path.read_text()) if self.path.exists() else {'cap_usd':str(HARD_LIMIT),'calls':{}}
            if Decimal(data['cap_usd']) != HARD_LIMIT:
                raise ValueError('Unexpected budget ceiling')
            yield data
            temp = self.path.with_suffix('.tmp')
            with temp.open('w') as stream:
                json.dump(data, stream, indent=2)
                stream.write('\n')
                stream.flush()
                os.fsync(stream.fileno())
            temp.replace(self.path)

    @staticmethod
    def exposure(data):
        return sum(Decimal(c.get('actual_usd',c['reserved_usd'])) for c in data['calls'].values())

    def reserve(self, model, body, label):
        maximum = reservation(model,body)
        with self.transaction() as data:
            if data.get('halted'):
                raise BudgetExceeded('Budget ledger halted: '+data['halted'])
            if self.exposure(data)+maximum > HARD_LIMIT:
                raise BudgetExceeded('New API budget cannot safely admit the next call')
            ident = uuid.uuid4().hex
            data['calls'][ident]={'model':model,'label':label,'reserved_usd':str(maximum),'status':'reserved'}
        return ident

    def settle(self, ident, response):
        problem = None
        with self.transaction() as data:
            row = data['calls'][ident]
            if row['status'] != 'reserved':
                raise ValueError('Reservation already settled')
            usage = response.get('usage')
            if usage is None:
                row['status']='unknown_cost'
            else:
                try:
                    if response.get('model') != row['model'] or response.get('service_tier') != 'default':
                        raise ValueError('Unpriced provider model or tier')
                    actual = cost(row['model'],usage)
                    row.update(status='settled',actual_usd=str(actual),usage=usage)
                    if actual > Decimal(row['reserved_usd']):
                        raise ValueError('Provider usage exceeds conservative reservation')
                except (ValueError,KeyError,TypeError) as exc:
                    problem=str(exc)
                    data['halted']=problem
                    row['status']='halted'
        if problem:
            raise BudgetExceeded(problem)

    def snapshot(self):
        with self.transaction() as data:
            return {'calls':len(data['calls']), 'exposure_usd':str(self.exposure(data)),
                    'known_usd':str(sum(Decimal(c.get('actual_usd','0')) for c in data['calls'].values())),
                    'unsettled':sum(c['status']!='settled' for c in data['calls'].values()),'cap_usd':str(HARD_LIMIT)}
