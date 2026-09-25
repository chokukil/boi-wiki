"""Correctable native-answer refusals: declared positions and closed codes only.

A refusal never carries draft text, quotations, source bytes, rejected input or
validator prose. It grants nothing and says nothing about semantic support.
"""
import re

RULE = re.compile(r'ANSWER_[A-Z0-9_]{1,110}')


class NativeAnswerRefusal(ValueError):
    """str() remains the reason code for every existing ValueError caller."""
    def __init__(self, code, *, status_code=409, **detail):
        super().__init__(code)
        self.status_code = status_code
        self.detail = {'reason_code': code, **detail}


def _declared(schema):
    known = set()
    def visit(value):
        if isinstance(value, dict):
            known.update(value.get('properties', {}))
            for child in value.values():visit(child)
        elif isinstance(value, list):
            for child in value:visit(child)
    visit(schema)
    return known


def draft_binding_refusal(error, draft, schema):
    """Locate each broken rule in the host's own draft; None when not only the draft failed."""
    known = _declared(schema);errors = []
    for item in error.errors(include_input=False, include_context=False, include_url=False)[:32]:
        if item['loc'][:1] != ('draft',):return None
        node = draft;parts = []
        for part in item['loc'][1:]:
            # A discriminated union reports its tag as a location; it is not a draft key.
            if isinstance(node, dict) and type(part) is str and part == node.get('kind') and part not in node:continue
            parts.append(part if type(part) is int or part in known else '<unexpected_field>')
            node = (node.get(part) if isinstance(node, dict) and type(part) is str
                else node[part] if isinstance(node, list) and type(part) is int and 0 <= part < len(node) else None)
        message = item['msg'].removeprefix('Value error, ')
        errors.append({'pointer':''.join(f'/{p}' for p in parts), 'type':item['type'],
            **({'rule':message} if item['type'] == 'value_error' and RULE.fullmatch(message) else {})})
    return NativeAnswerRefusal('DOMAIN_INTAKE_REQUEST_INVALID', status_code=422,
        validation_stage='draft_binding', validation_errors=errors)


def unresolved_meaning_refusal(targets):
    """Keep which selected target failed and its closed code; the exception text is dropped."""
    return NativeAnswerRefusal('ANSWER_EXPLAIN_EVIDENCE_UNRESOLVED', unresolved_targets=[
        {'asset_revision':t['asset_revision'], 'target_pointer':t['target_pointer'],
            **({'reason_code':t['reason_code']} if RULE.fullmatch(str(t.get('reason_code'))) else {})}
        for t in targets if t['binding_status'] != 'bound'][:32])
