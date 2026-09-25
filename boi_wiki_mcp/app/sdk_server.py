"""Official SDK 2 transport errors with a bounded, structured BoI diagnosis."""
import json
import re
from .concept_recovery import CONCEPT_RECOVERY_ACTIONS, concept_recovery

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import CallToolResult, TextContent
from pydantic import ValidationError


SCHEMA_ERROR_TYPES=frozenset({'missing','extra_forbidden','literal_error','enum',
    'union_tag_invalid','union_tag_not_found','too_short','too_long','string_type',
    'int_type','bool_type','list_type','dict_type','model_type','value_error',
    'less_than','less_than_equal','greater_than','greater_than_equal','string_pattern_mismatch'})
SAFE_INTENT_VALIDATION_RULES=frozenset({
    'QUALITY_MEASURE_DUPLICATE','ROWSET_MEMBERSHIP_REQUIRED',
    'ROWSET_MEMBERSHIP_INVALID','ROWSET_REVISION_REQUIRED',
    'QUALITY_INTENT_REVISION_REQUIRED','AGGREGATE_SCOPE_REVISION_REQUIRED',
    'ROOT_ABSENCE_REVISION_REQUIRED',
    'LATEST_GROUP_BY_FORBIDDEN','MIXED_LATEST_REDUCER_CONTRACT_REQUIRED',
})


def schema_errors(errors, schema):
    """Keep declared field names and positions, never input, prose or dynamic keys."""
    known={'body','query','path','header','cookie','<unexpected_field>'}
    def visit(value):
        if isinstance(value,dict):
            known.update(value.get('properties',{}))
            for child in value.values():visit(child)
        elif isinstance(value,list):
            for child in value:visit(child)
    visit(schema)
    if not isinstance(errors,list) or not 0<len(errors)<=32:return []
    safe=[]
    for error in errors:
        if (not isinstance(error,dict) or not isinstance(error.get('type'),str) or error['type'] not in SCHEMA_ERROR_TYPES
                or not isinstance(error.get('loc'),(list,tuple)) or len(error['loc'])>32):return []
        located={'type':error['type'],'loc':[
            part if (type(part) is int and 0<=part<=10_000_000) or (isinstance(part,str) and part in known)
            else '<unexpected_field>' for part in error['loc']]}
        rule=error.get('rule_code')
        if error['type']=='value_error' and isinstance(rule,str) and rule in SAFE_INTENT_VALIDATION_RULES:
            located['rule_code']=rule
        safe.append(located)
    return safe


DRAFT_RULE=re.compile(r'ANSWER_[A-Z0-9_]{1,110}')


def draft_errors(errors, schema, rules):
    """The same redaction for a draft position, plus its closed rule code; never a message."""
    if not isinstance(errors,list) or any(not isinstance(e,dict) or not isinstance(e.get('pointer'),str)
            or len(e['pointer'])>2048 for e in errors):return []
    located=schema_errors([{'type':e.get('type'),'loc':[int(p) if re.fullmatch(r'0|[1-9][0-9]{0,7}',p) else p
        for p in e['pointer'].split('/')[1:]]} for e in errors],schema)
    return [{'pointer':''.join(f'/{p}' for p in safe['loc']),'type':safe['type'],
        **({'rule':e['rule']} if isinstance(e.get('rule'),str) and DRAFT_RULE.fullmatch(e['rule']) and e['rule'] in rules else {})}
        for safe,e in zip(located,errors)]


def unresolved_targets(detail, allowed_codes):
    """Backend-resolved selection positions and closed codes; never exception prose."""
    targets=detail.get('unresolved_targets') if isinstance(detail,dict) else None
    if not isinstance(targets,list) or not 0<len(targets)<=32:return []
    safe=[]
    for target in targets:
        revision=target.get('asset_revision') if isinstance(target,dict) else None
        if (not isinstance(revision,dict) or set(revision)!={'ref','revision_digest'}
                or not isinstance(revision['ref'],str) or not re.fullmatch(r'[A-Za-z]{1,64}:sha256:[a-f0-9]{64}',revision['ref'])
                or not isinstance(revision['revision_digest'],str) or not re.fullmatch(r'sha256:[a-f0-9]{64}',revision['revision_digest'])
                or not isinstance(target.get('target_pointer'),str)
                or not re.fullmatch(r'(/([a-z_]{1,64}|0|[1-9][0-9]{0,7})){1,32}',target['target_pointer'])):return []
        code=target.get('reason_code')
        safe.append({'asset_revision':dict(revision),'target_pointer':target['target_pointer'],
            **({'reason_code':code} if isinstance(code,str) and code in allowed_codes else {})})
    return safe


def recovery_refs(detail):
    """Only backend-issued opaque references; these grant no execution or read authority."""
    if not isinstance(detail,dict):return {}
    result={}
    invocation=detail.get('invocation_id')
    if isinstance(invocation,str) and re.fullmatch(r'tool-invocation:sha256:[a-f0-9]{64}',invocation):
        result['invocation_id']=invocation
    execution=detail.get('execution_ref')
    if (isinstance(execution,dict) and set(execution)=={'ref','revision_digest'}
            and isinstance(execution['ref'],str) and re.fullmatch(r'Run:sha256:[a-f0-9]{64}',execution['ref'])
            and isinstance(execution['revision_digest'],str) and re.fullmatch(r'sha256:[a-f0-9]{64}',execution['revision_digest'])):
        result['execution_ref']=dict(execution)
    return result


class BoiApiError(RuntimeError):
    def __init__(self, status_code, body, *, allowed_codes):
        detail=body.get('detail') if isinstance(body,dict) else None
        code=detail.get('reason_code') if isinstance(detail,dict) else None
        if isinstance(code,str) and code in CONCEPT_RECOVERY_ACTIONS and status_code != 409:code=None
        self.diagnostic={'contract_version':'boi/mcp-error@1',
            'kind':'authorization' if status_code in (401,403) else 'backend',
            'status_code':status_code,'operation_outcome':'not_established','automatic_retry':False}
        if isinstance(code,str) and code in allowed_codes:
            self.diagnostic['reason_code']=code
            self.diagnostic.update(recovery_refs(detail))
            recovery=concept_recovery(status_code,code)
            if recovery:self.diagnostic['recovery']=recovery
            unresolved=unresolved_targets(detail,allowed_codes)
            if unresolved:self.diagnostic['unresolved_targets']=unresolved
        # draft_binding is the API's own coded re-validation of an authored draft.
        self.validation_stage=(detail.get('validation_stage') if isinstance(detail,dict)
            and status_code==422 and code=='DOMAIN_INTAKE_REQUEST_INVALID'
            and detail.get('validation_stage') in ('request_schema','draft_binding') else None)
        self.validation_errors=detail.get('validation_errors') if self.validation_stage else None
        self.draft_rules=frozenset(allowed_codes)
        # Existing specialized handlers can still decode the safe category.
        # Raw error bodies, source arguments and token-bearing URLs stay out.
        super().__init__(json.dumps({'status_code':status_code,'body':{'detail':{
            'reason_code':self.diagnostic.get('reason_code')}}}))


class BoiMCPServer(MCPServer):
    def _failure_result(self,name,value,errors=None,draft_rules=None):
        tool=self._tool_manager.get_tool(name)
        safe=(schema_errors(errors,tool.parameters if tool else {}) if draft_rules is None
            else draft_errors(errors,tool.parameters if tool else {},draft_rules))
        if safe:value={**value,'validation_errors':safe}
        value={**value,'tool':name}
        return CallToolResult(is_error=True,structured_content=value,
            content=[TextContent(type='text',text=json.dumps(value,ensure_ascii=False))])

    async def call_tool(self, name, arguments, context=None):
        try:
            return await super().call_tool(name,arguments,context)
        except Exception as error:
            # The SDK's pre-handler validation exception includes rejected input.
            # A validation failure inside a handler is wrapped differently and
            # cannot be classified as a safe argument correction here.
            if type(error) is ToolError and isinstance(error.__cause__,ValidationError):
                return self._failure_result(name,{'contract_version':'boi/mcp-error@1',
                    'kind':'backend','status_code':422,'reason_code':'DOMAIN_INTAKE_REQUEST_INVALID',
                    'validation_stage':'mcp_arguments','operation_outcome':'not_established',
                    'automatic_retry':False},error.__cause__.errors(include_input=False,include_context=False))
            # Tool.run wraps application errors. Only our typed exception may
            # publish a diagnosis; arbitrary SDK/server exception prose cannot.
            current=error
            for _ in range(8):
                if isinstance(current,BoiApiError):
                    value=dict(current.diagnostic)
                    if current.validation_errors is not None:value['validation_stage']=current.validation_stage
                    return self._failure_result(name,value,current.validation_errors,
                        current.draft_rules if current.validation_stage=='draft_binding' else None)
                current=current.__cause__
                if current is None:
                    break
            raise
