"""Explicitly initialize a new server ledger and scoped source policy; never reset state."""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib
import json
import os
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from boi_api.app.governed_runtime.ledger import GovernedRuntimeLedger
from boi_api.app.governed_runtime.release_rebuild import KnowledgeObjectStore
from boi_api.app.governed_runtime.source_intake_runtime import SourceIntakeRuntimePolicy


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-dir',type=Path,required=True)
    parser.add_argument('--principal',action='append',required=True)
    parser.add_argument('--valid-days',type=int,default=30)
    args=parser.parse_args()
    if not 1<=args.valid_days<=365:parser.error('--valid-days must be 1..365')
    now=datetime.now(timezone.utc)
    policy=SourceIntakeRuntimePolicy(contract_version='boi/source-intake-runtime-policy@0.1.0',
        principal_ids=args.principal,allowed_uses=['store','derive','cite','model_input'],visibility='private',
        effective_from=now,stale_after=now+timedelta(days=args.valid_days))
    root=args.state_dir.resolve();root.mkdir(parents=True,exist_ok=False,mode=0o700)
    GovernedRuntimeLedger(root/'ledger');KnowledgeObjectStore(root/'objects')
    raw=policy.model_dump_json(indent=2).encode()
    path=root/'source-policy.json'
    fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'wb') as stream:stream.write(raw)
    print(json.dumps({'BOI_SOURCE_INTAKE_ENABLED':'true','BOI_PROFILE_QUERY_LEDGER_ROOT':str(root/'ledger'),
        'BOI_PROFILE_QUERY_OBJECT_ROOT':str(root/'objects'),'BOI_SOURCE_INTAKE_POLICY_PATH':str(path),
        'BOI_SOURCE_INTAKE_POLICY_DIGEST':'sha256:'+hashlib.sha256(raw).hexdigest()},indent=2))


if __name__=='__main__':main()
