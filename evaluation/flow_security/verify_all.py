"""Offline dataset, source snapshot, outcome and privacy verification."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SHARED=ROOT/'evaluation/agent_security/results'


def main():
    freeze=json.loads((HERE/'freeze.json').read_text())
    for name,digest in freeze['sha256'].items():
        if hashlib.sha256((HERE/name).read_bytes()).hexdigest()!=digest:
            raise ValueError('Frozen input changed: '+name)
    runs=sorted(SHARED.glob('flow_*/SUMMARY.json'))
    if not runs:raise ValueError('No completed flow reports')
    frozen_runtime=json.loads((HERE/'runtime_freeze.json').read_text())['sha256']
    for result in runs:
        manifest=json.loads((result.parent/'manifest.json').read_text())
        if 'test' in result.parent.name or 'confirm' in result.parent.name:
            for name,digest in frozen_runtime.items():
                if name in manifest['source_sha256'] and manifest['source_sha256'][name]!=digest:
                    raise ValueError('Independent run differs from frozen implementation: '+name)
        subprocess.run([sys.executable,'-m','evaluation.flow_security.report',str(result.parent),'--check'],check=True)
        subprocess.run([sys.executable,'-m','evaluation.hosted.public_logs',str(result.parent),'--check'],check=True)
    confirmations=[SHARED/f'flow_confirm{i}' for i in (1,2,3)]
    if (SHARED/'FLOW_CONFIRMATION.json').exists():
        subprocess.run([sys.executable,'-m','evaluation.flow_security.confirmation_report',
                        *map(str,confirmations),'--check'],check=True)
    same=[SHARED/f'flow_confirm_same{i}' for i in (1,2,3)]
    if (SHARED/'FLOW_SAME_MODEL_CONFIRMATION.json').exists():
        subprocess.run([sys.executable,'-m','evaluation.flow_security.confirmation_report',
                        *map(str,same),'--candidate','flow','--out',str(SHARED/'FLOW_SAME_MODEL_CONFIRMATION'),'--check'],check=True)
    subprocess.run([sys.executable,'-m','evaluation.flow_security.accounting','--check'],check=True)
    print(f'Verified {len(runs)} flow batches against frozen data, code snapshots and delivered effects.')


if __name__=='__main__':main()
