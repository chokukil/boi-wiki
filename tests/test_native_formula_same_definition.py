"""Two observations may bind one definition; conflicting catalog rows remain errors."""
from copy import deepcopy
import pytest
from tests.test_native_formula_request import invoke
from tests.test_formula_preview import formula, rev
from tests.test_formula_evaluation import obs


def repeated_request():
    f = formula()
    f['contract_version'] = 'boi/formula-preview@2'
    f['parameters']['q'] = deepcopy(f['parameters']['p'])
    f['expression'] = {'kind': 'arithmetic', 'operator': 'subtract',
        'left': {'kind': 'parameter', 'binding': 'p'},
        'right': {'kind': 'parameter', 'binding': 'q'}}
    return {'formula': f, 'parameter_reviews': {'p': rev('c'), 'q': rev('c')},
        'time_policy': {'now': '2026-09-08T10:00:05Z',
            'max_age_seconds': 10, 'max_skew_seconds': 0},
        'observations': {**obs(1500), 'q': obs(1200)['p']}}


def test_same_definition_keeps_distinct_observations_and_both_authority_reads(monkeypatch):
    from boi_api.app.v2 import native_formula
    original = native_formula.resolve_formula_parameter
    calls = []
    def read(*args, **kwargs):
        calls.append(args[3])
        return original(*args, **kwargs)
    monkeypatch.setattr(native_formula, 'resolve_formula_parameter', read)
    result = invoke(monkeypatch, **repeated_request())
    assert result['evaluation']['status'] == 'known'
    assert result['evaluation']['value'] == '300'
    assert calls == ['p', 'q']
    assert set(result['parameter_resolutions']) == {'p', 'q'}


def test_same_identity_with_different_resolved_content_remains_ambiguous(monkeypatch):
    from boi_api.app.v2 import native_formula
    original = native_formula.resolve_formula_parameter
    def read(*args, **kwargs):
        result = original(*args, **kwargs)
        if args[3] == 'q':
            result = deepcopy(result)
            result['parameter']['parameter_name'] = 'conflicting name'
        return result
    monkeypatch.setattr(native_formula, 'resolve_formula_parameter', read)
    with pytest.raises(ValueError, match='SVID_PARAMETER_AMBIGUOUS'):
        invoke(monkeypatch, **repeated_request())
