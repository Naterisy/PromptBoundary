import unittest
from evaluation.agent_security.sandbox import Sandbox,SandboxError

class SandboxTests(unittest.TestCase):
    def test_actual_state_and_effects(self):
        s=Sandbox()
        a=[{'tool':'send_email','arguments':{'to':'a@example.test','subject':'x','body':'y'}},
           {'tool':'write_file','arguments':{'path':'report.txt','content':'source value'}},
           {'tool':'update_record','arguments':{'record_id':'r1','field':'label','value':'green'}}]
        s.apply(a)
        self.assertEqual(s.effects,a)
        self.assertEqual(s.state['files'],{'report.txt':'source value'})
        self.assertEqual(s.state['records'],{'r1':{'label':'green'}})
        self.assertEqual(len(s.state['outbox']),1)
        state=s.state;state['files'].clear()
        self.assertIn('report.txt',s.state['files'])

    def test_bad_batch_has_no_effects(self):
        for bad in [{'tool':'execute','arguments':{}},{'tool':'send_email','arguments':{'to':[],'subject':'x','body':'y'}}]:
            s=Sandbox()
            with self.assertRaises(SandboxError):s.apply([{'tool':'write_file','arguments':{'path':'x','content':'y'}},bad])
            self.assertEqual(s.effects,[])
            self.assertEqual(s.state,{'outbox':[],'files':{},'records':{}})

    def test_overwrite_and_multiple_distinct_effects(self):
        s=Sandbox()
        s.registry['write_file'](path='x',content='first')
        s.registry['write_file'](path='x',content='second')
        self.assertEqual(s.state['files']['x'],'second')
        self.assertEqual(len(s.effects),2)
