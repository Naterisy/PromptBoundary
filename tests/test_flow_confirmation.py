"""Statistical-unit and missingness checks using synthetic outcomes, no API calls."""
import copy
from decimal import Decimal
import unittest

from evaluation.flow_security.confirmation_report import DEFAULT_MODEL, summarize, markdown


LABELS = {
    'attack-a': {'is_attack': True, 'source_fact_sentinel': False, 'category': 'indirect'},
    'attack-b': {'is_attack': True, 'source_fact_sentinel': False, 'category': 'role'},
    'normal': {'is_attack': False, 'source_fact_sentinel': False, 'category': 'normal'},
    'fact': {'is_attack': False, 'source_fact_sentinel': True, 'category': 'source_fact'},
}


def report(attack_a=(True, False), attack_b=(True, False), normal=(False, True)):
    pairs = {'attack-a': attack_a, 'attack-b': attack_b, 'normal': normal, 'fact': (True, False)}
    rows, groups = [], {}
    for index, arm in enumerate(('raw', 'hybrid')):
        group = []
        for cid, labels in LABELS.items():
            value = pairs[cid][index]
            row = {'model': DEFAULT_MODEL, 'arm': arm, 'case': cid, **labels,
                   'transport_error': value is None,
                   'attack_success': value if labels['is_attack'] else None,
                   'normal_pass': value if cid == 'normal' else None,
                   'false_refusal': (not value) if cid == 'normal' and value is not None else None,
                   'source_fact_error': value if cid == 'fact' else None}
            rows.append(row); group.append(row)
        def ratio(key):
            values = [r[key] for r in group if r[key] is not None]
            return {'count': sum(values), 'n': len(values)}
        groups[arm] = {key: ratio(key) for key in ('attack_success', 'normal_pass', 'false_refusal', 'source_fact_error')}
        groups[arm].update(technical_errors=sum(r['transport_error'] for r in group), total_cases=len(group),
                           calls=len(group) * (index + 1), priced_responses=len(group) * (index + 1),
                           known_usd='0.0100', latency_ms={'p50': 1, 'p95': 2}, status_counts={'fixture': len(group)})
    return {'suite_sha256': 'identical-frozen-suite', 'models': {DEFAULT_MODEL: groups}, 'cases': rows,
            'hybrid_reviewer_model': 'gpt-5.4-mini-2026-03-17'}


class FlowConfirmationTests(unittest.TestCase):
    def test_case_clusters_receive_equal_weight_not_individual_api_calls(self):
        # Case A improves on all 3 runs. B regresses once and has 2 missing pairs.
        # Equal case weights yield 0 pp; pooling 4 observed repeats would yield 50 pp.
        reports = [report(attack_b=(False, True)), report(attack_b=(None, True)), report(attack_b=(None, True))]
        result = summarize(reports, ['r1', 'r2', 'r3'])
        attack = result['paired']['attack_success']
        self.assertEqual(attack['case_mean_benefit_pp'], 0)
        self.assertEqual(attack['missing_pairs'], 2)
        self.assertEqual(attack['available_pairs'], 4)
        self.assertEqual(attack['expected_pairs'], 6)
        self.assertEqual(attack['observed_clusters'], 2)
        self.assertEqual(attack['case_cluster_bootstrap95_pp'], [-100, 100])
        self.assertEqual([c['available_pairs'] for c in attack['clusters']], [3, 1])

    def test_missing_pairs_never_count_as_safe_wins(self):
        result = summarize([report(attack_a=(True, None), attack_b=(None, None))], ['r1'])
        attack = result['paired']['attack_success']
        self.assertEqual(attack['missing_pairs'], 2)
        self.assertEqual(attack['available_pairs'], 0)
        self.assertIsNone(attack['case_mean_benefit_pp'])
        self.assertIsNone(attack['case_cluster_bootstrap95_pp'])
        self.assertEqual(attack['cases_without_pairs'], ['attack-a', 'attack-b'])
        self.assertEqual(result['totals']['technical_errors'], 3)

    def test_normal_utility_has_opposite_direction_to_failure_metrics(self):
        result = summarize([report()], ['r1'])
        for metric in ('attack_success', 'normal_pass', 'false_refusal'):
            self.assertEqual(result['paired'][metric]['case_mean_benefit_pp'], 100)
            self.assertEqual(result['paired'][metric]['case_cluster_bootstrap95_pp'], [100, 100])
        regression = summarize([report(normal=(True, False))], ['r1'])
        self.assertEqual(regression['paired']['normal_pass']['case_mean_benefit_pp'], -100)
        self.assertEqual(regression['paired']['false_refusal']['case_mean_benefit_pp'], -100)

    def test_fact_sentinels_are_not_injection_or_normal_clusters(self):
        result = summarize([report(), report()], ['r1', 'r2'])
        self.assertEqual(result['unique_cases'], 4)
        self.assertEqual(result['attack_case_clusters'], 2)
        self.assertEqual(result['normal_case_clusters'], 1)
        self.assertEqual(result['source_fact_sentinels_excluded'], 1)
        for metric in result['paired'].values():
            self.assertNotIn('fact', [c['case'] for c in metric['clusters']])
        self.assertIn('not new independent cases', markdown(result))

    def test_all_runs_and_both_arm_costs_are_retained(self):
        result = summarize([report(), report(), report()], ['r1', 'r2', 'r3'])
        self.assertEqual(Decimal(result['totals']['known_usd']), Decimal('0.06'))
        self.assertEqual(result['totals']['calls'], 36)
        self.assertEqual(result['repetitions'], 3)
        self.assertEqual(result['bootstrap_samples'], 10000)
        self.assertEqual(result['cluster_seed'], 181)

    def test_different_suites_cases_or_reviewer_cannot_be_silently_combined(self):
        for change in ('suite', 'case', 'reviewer'):
            other = report()
            if change == 'suite':
                other['suite_sha256'] = 'different'
            elif change == 'case':
                other['cases'][0]['case'] = 'different-case'
            else:
                other['hybrid_reviewer_model'] = 'different-reviewer'
            with self.subTest(change=change), self.assertRaises(ValueError):
                summarize([report(), other], ['r1', 'r2'])

    def test_missing_or_duplicate_rows_require_explicit_run_classification(self):
        for kind in ('missing', 'duplicate'):
            broken = report()
            if kind == 'missing':
                broken['cases'].pop()
            else:
                broken['cases'].append(copy.deepcopy(broken['cases'][0]))
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                summarize([broken], ['r1'])
        with self.assertRaises(ValueError):
            summarize([report(), report()], ['same-run', 'same-run'])

    def test_technical_error_with_behavior_score_is_rejected(self):
        broken = report()
        broken['cases'][0]['transport_error'] = True
        with self.assertRaisesRegex(ValueError, 'Technical error'):
            summarize([broken], ['r1'])

    def test_same_model_flow_candidate_has_no_reviewer_and_uses_identical_clusters(self):
        baseline = report()
        flow = copy.deepcopy(baseline)
        flow['hybrid_reviewer_model'] = None
        flow['models'][DEFAULT_MODEL]['flow'] = flow['models'][DEFAULT_MODEL].pop('hybrid')
        for row in flow['cases']:
            if row['arm'] == 'hybrid':
                row['arm'] = 'flow'
        result = summarize([flow], ['same1'], second='flow')
        self.assertTrue(result['same_model_comparison'])
        self.assertIsNone(result['reviewer_model'])
        self.assertEqual(result['paired'], summarize([baseline], ['hybrid1'])['paired'])
        self.assertIn('post-holdout', result['selection_stage'])
        self.assertIn('no semantic reviewer', markdown(result))
        flow['hybrid_reviewer_model'] = 'unexpected-reviewer'
        with self.assertRaisesRegex(ValueError, 'Reviewer metadata'):
            summarize([flow], ['same1'], second='flow')

    def test_hybrid_requires_reviewer_metadata_and_missing_generator_is_rejected(self):
        missing_reviewer = report()
        missing_reviewer['hybrid_reviewer_model'] = None
        with self.assertRaisesRegex(ValueError, 'Reviewer metadata'):
            summarize([missing_reviewer], ['hybrid1'])
        wrong_model = report()
        for row in wrong_model['cases']:
            row['model'] = 'a-different-generator'
        with self.assertRaises(ValueError):
            summarize([wrong_model], ['wrong-model'])

    def test_reproducible_finite_bootstrap_with_fractional_case_means(self):
        reports = [report(), report(attack_a=(False, False)), report(attack_b=(False, False))]
        one = summarize(reports, ['r1', 'r2', 'r3'])
        two = summarize(reports, ['r1', 'r2', 'r3'])
        self.assertEqual(one, two)
        self.assertEqual(one['paired']['attack_success']['case_mean_benefit_pp'], 66.6666666667)


if __name__ == '__main__':
    unittest.main()
