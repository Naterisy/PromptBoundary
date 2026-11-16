import copy
import unittest
from evaluation.hosted.public_logs import redact


class JournalPrivacyTests(unittest.TestCase):
    def test_account_metadata_removed_without_altering_observable_results_or_costs(self):
        response={'id':'example-response','model':'example-model','service_tier':'default',
                  'usage':{'input_tokens':10,'output_tokens':20},
                  'access_programs':['FICTIONAL_ACCOUNT_GROUP'],'metadata':{'owner':'fictional-owner'},
                  'output':[{'type':'message','content':[{'type':'output_text','text':'actual delivered text'}]}]}
        record={'response':response};before=copy.deepcopy(response)
        self.assertTrue(redact(record))
        self.assertNotIn('access_programs',response)
        self.assertNotIn('metadata',response)
        for key in ('id','model','service_tier','usage','output'):
            self.assertEqual(response[key],before[key])
        self.assertEqual(len(response['access_programs_redacted']['sha256']),64)
        self.assertFalse(redact(record))


if __name__=='__main__':unittest.main()
