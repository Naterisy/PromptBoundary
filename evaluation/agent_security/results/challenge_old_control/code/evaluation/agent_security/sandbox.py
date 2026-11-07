"""Inert tool environment with real in-memory state changes and a shared schema.

No filesystem, network, mail delivery or external service is reachable.
"""
import copy

TOOL_ARGUMENTS={'send_email':{'to','subject','body'},'write_file':{'path','content'},
                'update_record':{'record_id','field','value'}}


class SandboxError(ValueError):
    pass


def valid_effects(actions):
    return (isinstance(actions,list) and all(isinstance(a,dict) and set(a)=={'tool','arguments'}
        and isinstance(a['tool'],str) and a['tool'] in TOOL_ARGUMENTS
        and isinstance(a['arguments'],dict) and set(a['arguments'])==TOOL_ARGUMENTS[a['tool']]
        and all(isinstance(v,str) for v in a['arguments'].values()) for a in actions))


class Sandbox:
    def __init__(self):
        self._outbox=[];self._files={};self._records={};self._effects=[]
        self.registry={name:self._callback(name) for name in TOOL_ARGUMENTS}

    def _callback(self,tool):
        def callback(**arguments):
            action={'tool':tool,'arguments':arguments}
            if not valid_effects([action]):raise SandboxError('Invalid tool arguments')
            args=copy.deepcopy(arguments)
            if tool=='send_email':self._outbox.append(args)
            elif tool=='write_file':self._files[args['path']]=args['content']
            else:self._records.setdefault(args['record_id'],{})[args['field']]=args['value']
            self._effects.append({'tool':tool,'arguments':args})
            return {'completed':True,'effect_index':len(self._effects)-1}
        return callback

    def apply(self,actions):
        # Invalid batches have no partial effects in either baseline or controller.
        if not valid_effects(actions):raise SandboxError('Invalid action batch')
        return [self.registry[a['tool']](**a['arguments']) for a in actions]

    @property
    def effects(self):return copy.deepcopy(self._effects)

    @property
    def state(self):
        return copy.deepcopy({'outbox':self._outbox,'files':self._files,'records':self._records})
