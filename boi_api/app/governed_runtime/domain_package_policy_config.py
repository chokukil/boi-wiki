"""Read server-owned HOTL criteria once at startup; never accept request policy."""
import json
from pathlib import Path

from .domain_package_contract import DomainPackagePolicy


def load_domain_package_policies(path):
    if not path:
        return ()
    try:
        source = Path(path)
        if not source.is_file() or source.stat().st_size > 1048576:
            raise ValueError()
        def unique(pairs):
            value = {}
            for key, item in pairs:
                if key in value:
                    raise ValueError()
                value[key] = item
            return value
        value = json.loads(source.read_text(encoding='utf-8'), object_pairs_hook=unique)
        if set(value) != {'contract_version','policies'} or value['contract_version'] != 'boi/domain-package-policy-config@1':
            raise ValueError()
        if not isinstance(value['policies'], list) or len(value['policies']) > 100:
            raise ValueError()
        policies = tuple(DomainPackagePolicy.model_validate(p) for p in value['policies'])
        if len({p.team_id for p in policies}) != len(policies):
            raise ValueError()
        return policies
    except (OSError, ValueError, TypeError, KeyError):
        raise ValueError('DOMAIN_PACKAGE_SERVER_POLICY_CONFIG_INVALID') from None
