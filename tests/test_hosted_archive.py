"""Keep historical evidence reproducible while allowing new transport fixes."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evaluation.hosted import archive
from promptboundary.responses import chat_result as current_chat_result


class HostedArchiveTests(unittest.TestCase):
    def test_original_phase_behavior_is_reconstructed_not_regraded(self):
        response = {'status': 'completed', 'model': 'fixture', 'output': [
            {'type': 'message', 'role': 'assistant', 'phase': 'commentary',
             'content': [{'type': 'output_text', 'text': 'I will inspect it. '}]},
            {'type': 'message', 'role': 'assistant', 'phase': 'final_answer',
             'content': [{'type': 'output_text', 'text': '{"answer":4}'}]},
        ]}
        old = archive.historical_chat_result()(response)['choices'][0]['message']['content']
        current = current_chat_result(response)['choices'][0]['message']['content']
        self.assertEqual(old, 'I will inspect it. {"answer":4}')
        self.assertEqual(current, '{"answer":4}')

    def test_exact_historical_sha_is_preserved(self):
        path = archive.verified_snapshot_path('promptboundary/responses.py', archive.RESPONSES_SHA256)
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), archive.RESPONSES_SHA256)

    def test_unknown_historical_hash_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'no pinned snapshot'):
            archive.verified_snapshot_path('promptboundary/responses.py', '0' * 64)

    def test_modified_snapshot_is_rejected_before_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            altered = Path(tmp) / 'responses.py'
            altered.write_text('raise AssertionError("must never import changed snapshot")\n')
            with patch.object(archive, 'SNAPSHOTS', {
                ('promptboundary/responses.py', archive.RESPONSES_SHA256): altered
            }), self.assertRaisesRegex(ValueError, 'SHA-256 verification'):
                archive.historical_chat_result()

    def test_other_sources_are_not_permitted_to_drift(self):
        source = 'promptboundary/upstream.py'
        digest = hashlib.sha256((archive.ROOT / source).read_bytes()).hexdigest()
        self.assertEqual(archive.verified_snapshot_path(source, digest), archive.ROOT / source)
        with self.assertRaisesRegex(ValueError, 'no pinned snapshot'):
            archive.verified_snapshot_path(source, '0' * 64)

    def test_manifest_cannot_select_arbitrary_external_python(self):
        for name in ('/tmp/other.py', '../other.py'):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'Invalid experiment source path'):
                archive.verified_snapshot_path(name, archive.RESPONSES_SHA256)


if __name__ == '__main__':
    unittest.main()
