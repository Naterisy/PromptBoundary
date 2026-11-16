"""Exploratory repeated-case stability; repetitions are not new independent cases."""
import argparse
from decimal import Decimal
import json
import math
from pathlib import Path
import random

SEED = 181
SAMPLES = 10000
DEFAULT_MODEL = 'gpt-4.1-mini-2025-04-14'
DEFAULT_OUT = Path(__file__).resolve().parents[1] / 'agent_security/results/FLOW_CONFIRMATION'


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _metric(lookups, cases, first, second, metric):
    normal = metric != 'attack_success'
    eligible = {cid: info for cid, info in cases.items()
                if not info['source_fact_sentinel'] and info['is_attack'] != normal}
    clusters, missing = [], 0
    for cid in sorted(eligible):
        differences = []
        for lookup in lookups:
            a, b = lookup[first, cid][metric], lookup[second, cid][metric]
            # Technical errors must not become zero-valued safe completions.
            if a is None or b is None:
                missing += 1
                continue
            _require(type(a) is bool and type(b) is bool, 'Behavior metrics must be bool or null')
            differences.append(int(b) - int(a) if metric == 'normal_pass' else int(a) - int(b))
        if differences:
            clusters.append({'case': cid, 'available_pairs': len(differences),
                             'differences': differences,
                             'mean_benefit': round(math.fsum(differences) / len(differences), 10)})
    # Do not round intermediate means before bootstrap/aggregation.
    means = [math.fsum(c['differences']) / c['available_pairs'] for c in clusters]
    rng = random.Random(SEED)
    samples = sorted(math.fsum(rng.choice(means) for _ in means) / len(means)
                     for _ in range(SAMPLES)) if means else []
    return {'clusters': clusters, 'eligible_cases': len(eligible), 'observed_clusters': len(clusters),
            'cases_without_pairs': sorted(set(eligible) - {c['case'] for c in clusters}),
            'expected_pairs': len(eligible) * len(lookups),
            'available_pairs': sum(c['available_pairs'] for c in clusters), 'missing_pairs': missing,
            'case_mean_benefit_pp': round(100 * math.fsum(means) / len(means), 10) if means else None,
            'case_cluster_bootstrap95_pp': [round(100 * samples[249], 10), round(100 * samples[9749], 10)] if samples else None}


def summarize(reports, run_names, model=DEFAULT_MODEL, first='raw', second='hybrid'):
    """Analyze stored per-case results; never ask a tested model to grade itself."""
    _require(first == 'raw' and second in ('hybrid', 'flow'), 'Unsupported comparison arms')
    _require(reports and len(reports) == len(run_names), 'Need one report per run')
    _require(len(set(run_names)) == len(run_names), 'Repeated run directory')
    suite = reports[0]['suite_sha256']
    lookups, reference, per_run = [], None, []
    totals = {'calls': 0, 'priced_responses': 0, 'technical_errors': 0}
    dollars = Decimal(0)
    reviewer_models = set()
    for name, report in zip(run_names, reports):
        _require(report['suite_sha256'] == suite, 'Repetitions used different suites')
        _require(model in report['models'], 'Generator model is missing')
        rows = [row for row in report['cases'] if row['model'] == model and row['arm'] in (first, second)]
        lookup = {(r['arm'], r['case']): r for r in rows}
        _require(len(lookup) == len(rows), 'Duplicate case row')
        ids = {r['case'] for r in rows}
        _require(ids and all((arm, cid) in lookup for cid in ids for arm in (first, second)),
                 'Missing case row; complete or explicitly classify the run first')
        info = {}
        for cid in sorted(ids):
            meta = {key: lookup[first, cid][key] for key in ('is_attack', 'source_fact_sentinel', 'category')}
            _require(all(lookup[second, cid][key] == value for key, value in meta.items()),
                     'Arm case labels differ')
            _require(type(meta['is_attack']) is bool and type(meta['source_fact_sentinel']) is bool,
                     'Invalid case labels')
            info[cid] = meta
            for arm in (first, second):
                row = lookup[arm, cid]
                if row.get('transport_error'):
                    _require(all(row[key] is None for key in ('attack_success', 'normal_pass', 'false_refusal')),
                             'Technical error contains behavioral success/failure metrics')
        if reference is None:
            reference = info
        else:
            _require(info == reference, 'Repetitions changed case IDs or labels')
        arms = {}
        for arm in (first, second):
            _require(arm in report['models'][model], 'Comparison arm missing')
            group = report['models'][model][arm]
            arms[arm] = {key: group[key] for key in ('attack_success', 'normal_pass', 'false_refusal',
                          'source_fact_error', 'technical_errors', 'total_cases', 'calls', 'priced_responses',
                          'known_usd', 'latency_ms', 'status_counts')}
            for key in totals:
                totals[key] += group[key]
            dollars += Decimal(group['known_usd'])
        per_run.append({'run': name, 'arms': arms})
        reviewer = report.get('hybrid_reviewer_model')
        _require((second == 'flow' and reviewer is None) or
                 (second == 'hybrid' and isinstance(reviewer, str) and bool(reviewer)),
                 'Reviewer metadata does not match the comparison arm')
        reviewer_models.add(reviewer)
        lookups.append(lookup)
    _require(len(reviewer_models) == 1, 'Reviewer changed between repeated runs')
    _require(all(math.isfinite(float(r['models'][model][arm]['known_usd'])) for r in reports
                 for arm in (first, second)), 'Invalid run cost')
    totals['known_usd'] = str(dollars)
    return {
        'method': 'same_case_repeated_sampling_stability', 'model': model,
        'selection_stage': 'post-holdout selected comparison; exploratory repeated-case confirmation',
        'same_model_comparison': second == 'flow',
        'reviewer_model': next(iter(reviewer_models)), 'from_arm': first, 'to_arm': second,
        'suite_sha256': suite, 'runs': run_names, 'repetitions': len(reports),
        'unique_cases': len(reference),
        'attack_case_clusters': sum(c['is_attack'] and not c['source_fact_sentinel'] for c in reference.values()),
        'normal_case_clusters': sum(not c['is_attack'] and not c['source_fact_sentinel'] for c in reference.values()),
        'source_fact_sentinels_excluded': sum(c['source_fact_sentinel'] for c in reference.values()),
        'cluster_seed': SEED, 'bootstrap_samples': SAMPLES,
        'bootstrap_interval': 'percentile: sorted samples 250 and 9750, one-based',
        'per_run': per_run, 'totals': totals,
        'paired': {metric: _metric(lookups, reference, first, second, metric)
                   for metric in ('attack_success', 'normal_pass', 'false_refusal')},
        'limitations': [
            'Exploratory confirmation of a model and method selected after observing the primary holdout; no multiplicity correction.',
            'Repeated cases are not additional independent scenarios or a new holdout.',
            'Intervals are conditional on the authored case clusters and observed repetitions; tactic dependence is unmodeled.',
            'Technical errors are missing paired evidence, never safe or successful outcomes.',
            'Missing pairs may be nonrandom; available-case averages do not establish noninferiority.',
            'Fact predicates approximate semantic utility; consult the independent audit and all raw outputs.',
            'Known USD is usage-priced API cost, not an invoice; unpriced responses require the shared reservation ledger.',
        ],
    }


def confirmation(directories, model=DEFAULT_MODEL, candidate='hybrid'):
    reports = [json.loads((directory / 'SUMMARY.json').read_text()) for directory in directories]
    return summarize(reports, [directory.name for directory in directories], model, second=candidate)


def _fraction(value):
    return f"{value['count']}/{value['n']}"


def markdown(result):
    lines = ['# Repeated-case flow confirmation', '',
             f"Generator: `{result['model']}`. Comparison: `{result['from_arm']}` → `{result['to_arm']}`.",
             (f"Hybrid reviewer: `{result['reviewer_model']}`." if result['reviewer_model'] is not None
              else 'Same-model comparison; no semantic reviewer.'), '',
             'This comparison was selected after the primary holdout was observed. It is exploratory confirmation, '
             'not a new independent validation of the selected method.', '',
             f"The same {result['unique_cases']} cases were sampled {result['repetitions']} times: "
             f"{result['attack_case_clusters']} injection cases, {result['normal_case_clusters']} normal cases, "
             f"and {result['source_fact_sentinels_excluded']} separately reported factual-poisoning sentinels. "
             'These are repeated measurements, not new independent cases.', '',
             '| Run | Arm | Attacks | Normal pass | False refusal | Technical errors | Calls | Known USD |',
             '|---|---|---:|---:|---:|---:|---:|---:|']
    for run in result['per_run']:
        for arm, group in run['arms'].items():
            lines.append(f"| {run['run']} | {arm} | {_fraction(group['attack_success'])} | "
                         f"{_fraction(group['normal_pass'])} | {_fraction(group['false_refusal'])} | "
                         f"{group['technical_errors']} | {group['calls']} | {group['known_usd']} |")
    lines += ['', '| Paired endpoint | Mean benefit (pp) | 95% case-cluster bootstrap (pp) | Clusters | Missing pairs |',
              '|---|---:|---:|---:|---:|']
    for metric, group in result['paired'].items():
        lines.append(f"| {metric} | {group['case_mean_benefit_pp']} | {group['case_cluster_bootstrap95_pp']} | "
                     f"{group['observed_clusters']}/{group['eligible_cases']} | {group['missing_pairs']} |")
    total = result['totals']
    lines += ['', 'Positive benefit means fewer executed attacks or false refusals, or more normal task completions. '
              'Each case is averaged over its available paired repetitions, then cases are sampled with replacement '
              'as whole clusters (10,000 draws, seed 181). Missing technical outcomes stay null. '
              'Factual-poisoning sentinels are excluded from injection and normal-task denominators.', '',
              f"Selected-arm totals: {total['calls']} API calls, {total['priced_responses']} priced responses, "
              f"{total['technical_errors']} technical errors, USD {total['known_usd']} usage-priced cost.", '',
              *['- ' + limitation for limitation in result['limitations']], '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directories', type=Path, nargs='+')
    parser.add_argument('--model', default=DEFAULT_MODEL)
    parser.add_argument('--candidate', choices=('hybrid', 'flow'), default='hybrid')
    parser.add_argument('--out', type=Path, default=DEFAULT_OUT)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    result = confirmation(args.directories, args.model, args.candidate)
    for suffix, content in [('json', json.dumps(result, ensure_ascii=False, indent=2) + '\n'),
                            ('md', markdown(result))]:
        destination = args.out.with_suffix('.' + suffix)
        if args.check:
            _require(destination.read_text() == content, 'Stale confirmation report: ' + str(destination))
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content)
    print(f"Verified {result['repetitions']} repetitions of {result['unique_cases']} unique cases")


if __name__ == '__main__':
    main()
