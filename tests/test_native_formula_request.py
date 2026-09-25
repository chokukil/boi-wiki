"""Request boundary tests: synthetic authority; real typed compiler/interpreters."""
import importlib.util
import pytest
from tests.test_native_svid_consumption import installed
from tests.test_formula_preview import formula, cmp, units, rev
from tests.test_formula_evaluation import obs


def invoke(monkeypatch, **changes):
    installed(monkeypatch)
    name='boi_api.app.v2.native_formula'
    assert importlib.util.find_spec(name), 'Native Formula request boundary is missing'
    module=__import__(name,fromlist=['preview_native_formula'])
    value={'formula':formula(cmp()),'parameter_reviews':{'p':rev('c')},
        'unit_definitions':units(),'observations':obs(1000),
        'time_policy':{'now':'2026-09-08T10:00:05Z','max_age_seconds':10,'max_skew_seconds':None}}
    value.update(changes)
    return module.preview_native_formula('work','auth',value)


def test_request_computes_inclusive_boundary_without_control_authority(monkeypatch):
    result=invoke(monkeypatch)
    assert result['evaluation']['value'] is True
    assert result['evaluation']['status']=='known'
    assert result['equipment_execution'] is False
    assert result['unit_definition_authority']=='caller_supplied_candidate'
    assert result['parameter_resolutions']['p']['parameter']['identity']['model']=='M1'


def test_changed_operator_and_missing_observation_use_same_request_path(monkeypatch):
    assert invoke(monkeypatch,formula=formula(cmp('lt')))['evaluation']['value'] is False
    result=invoke(monkeypatch,observations={})
    assert result['evaluation']['status']=='unknown'
    assert 'missing' in result['evaluation']['reasons']


def test_unreviewed_parameter_cannot_enter_formula_compiler(monkeypatch):
    with pytest.raises(ValueError,match='NATIVE_FORMULA_REVIEW_BINDINGS_MISMATCH'):
        invoke(monkeypatch,parameter_reviews={})
    f=formula(cmp());f['parameters']['p']['identity']['model']='Other'
    with pytest.raises(ValueError,match='SVID_PARAMETER_NOT_FOUND'):
        invoke(monkeypatch,formula=f)


def test_unknown_preview_observations_are_not_silently_ignored(monkeypatch):
    with pytest.raises(ValueError,match='NATIVE_FORMULA_UNKNOWN_OBSERVATION'):
        invoke(monkeypatch,observations={**obs(1000),'unbound':obs(1)['p']})


def test_time_policy_is_not_invented_for_supplied_observations(monkeypatch):
    with pytest.raises(ValueError,match='NATIVE_FORMULA_EVALUATION_INPUTS_REQUIRED'):
        invoke(monkeypatch,time_policy=None)
    result=invoke(monkeypatch,observations=None,time_policy=None)
    assert result['evaluation'] is None
    assert result['compilation']['result_type']=='boolean'


def test_hypothetical_value_computes_without_inventing_observation_time(monkeypatch):
    scenario={key:{field:value for field,value in sample.items() if field!='observed_at'}
        for key,sample in obs(1000).items()}
    result=invoke(monkeypatch,observations=None,time_policy=None,scenario_values=scenario)
    assert result['evaluation']['status']=='known'
    assert result['evaluation']['value'] is True
    assert result['evaluation']['input_mode']=='hypothetical'
    assert result['evaluation']['definition_time_verified'] is False
    assert result['observation_origin']=='caller_supplied_hypothetical'
    assert result['time_policy_authority']=='not_applicable_hypothetical'
    assert result['observation_unit_definitions']==[]
    assert result['scenario_unit_definitions']
    assert result['equipment_execution'] is False
    assert result['semantic_truth_proven'] is False


def test_hypothetical_values_keep_revision_unit_and_mode_boundaries(monkeypatch):
    scenario={key:{field:value for field,value in sample.items() if field!='observed_at'}
        for key,sample in obs(1000).items()}
    with pytest.raises(ValueError,match='NATIVE_FORMULA_INPUT_MODES_EXCLUSIVE'):
        invoke(monkeypatch,scenario_values=scenario)
    with pytest.raises(ValueError,match='NATIVE_FORMULA_UNKNOWN_SCENARIO_VALUE'):
        invoke(monkeypatch,observations=None,time_policy=None,
            scenario_values={**scenario,'unbound':next(iter(scenario.values()))})
    changed={key:{**sample,'revision':rev('e')} for key,sample in scenario.items()}
    with pytest.raises(ValueError,match='FORMULA_OBSERVATION_REVISION_MISMATCH'):
        invoke(monkeypatch,observations=None,time_policy=None,scenario_values=changed)
    nulls={key:{**sample,'value':None} for key,sample in scenario.items()}
    result=invoke(monkeypatch,observations=None,time_policy=None,scenario_values=nulls)
    assert result['evaluation']['status']=='unknown'


def test_conditional_definition_scenario_uses_current_resolved_context_once(monkeypatch):
    from copy import deepcopy
    from boi_api.app.v2 import native_formula as native
    from boi_api.app.governed_runtime.formula_preview import UnitDefinition
    from tests.test_formula_preview import row
    candidate=row()
    candidate['identity']={'knowledge_id':'knowledge-fixture','parameter_id':'reading'}
    selection=deepcopy({key:candidate[key] for key in
        ('identity','revision','component','quantity','unit')})
    expression=formula(cmp())
    expression['contract_version']='boi/formula-preview@2'
    expression['parameters']={'p':selection}
    context={'contract_digest':'sha256:'+'9'*64,
        'definition':{'assumptions':[{'id':'scope','statement':'Use this source-local scope',
            'meaning_pointers':['/parameters/0/uncertainties/0']}]},
        'input_scope':[{'id':'channel','expected_value':{'kind':'text','value':'synthetic-channel-z'}}]}
    resolved={'parameter':candidate,'calculation_context':context,
        'knowledge_qualification':None,'required_unit_definition':None,
        'quantity_definition_resolution':None}
    monkeypatch.setattr(native,'resolve_formula_parameter',lambda *a,**k:deepcopy(resolved))
    monkeypatch.setattr(native,'resolve_native_units',lambda *a,**k:(
        [UnitDefinition.model_validate(x) for x in units()],{}))
    scenario={key:{field:value for field,value in sample.items() if field!='observed_at'}
        for key,sample in obs(1000).items()}
    request={'formula':expression,'knowledge_qualifications':{'p':rev('c')},
        'unit_definitions':units(),'scenario_values':scenario}
    unbound=native.preview_native_formula('work','auth',request)
    assert unbound['evaluation']['status']=='unknown'
    assert unbound['evaluation']['reasons']==['formula_context_missing']
    bound=native.preview_native_formula('work','auth',{
        **request,'conditional_definition_scenario':True})
    assert bound['compilation']==unbound['compilation']
    assert bound['evaluation']['status']=='known' and bound['evaluation']['value'] is True
    assert bound['calculation_context']['status']=='satisfied'
    assert bound['calculation_context']['input_provenance']==(
        'engine_assembled_conditional_current_definition')
    assert bound['calculation_context']['world_applicability']=='not_verified'
    assert bound['equipment_execution'] is False and bound['semantic_truth_proven'] is False
    retained={'request':{**request,'conditional_definition_scenario':True},
        'result':bound}
    monkeypatch.setattr(native,'read_formula_execution',lambda *a,**k:deepcopy(retained))
    assert native.read_current_formula_execution('work','auth','saved')['result'][
        'calculation_context']==bound['calculation_context']
    changed_context=deepcopy(resolved)
    changed_context['calculation_context']['contract_digest']='sha256:'+'8'*64
    monkeypatch.setattr(native,'resolve_formula_parameter',lambda *a,**k:deepcopy(changed_context))
    with pytest.raises(ValueError,match='NATIVE_FORMULA_CONTEXT_DEFINITION_MISMATCH'):
        native.read_current_formula_execution('work','auth','saved')
    monkeypatch.setattr(native,'resolve_formula_parameter',lambda *a,**k:deepcopy(resolved))
    with pytest.raises(ValueError,match='NATIVE_FORMULA_CONDITIONAL_CONTEXT_UNAVAILABLE'):
        native.preview_native_formula('work','auth',{
            **request,'conditional_definition_scenario':True,
            'scenario_values':{'p':{**scenario['p'],'revision':rev('e')}}})
    without_context=deepcopy(resolved)
    without_context['calculation_context']=None
    monkeypatch.setattr(native,'resolve_formula_parameter',lambda *a,**k:deepcopy(without_context))
    with pytest.raises(ValueError,match='NATIVE_FORMULA_CONDITIONAL_CONTEXT_UNAVAILABLE'):
        native.preview_native_formula('work','auth',{
            **request,'conditional_definition_scenario':True})
    monkeypatch.setattr(native,'resolve_formula_parameter',lambda *a,**k:deepcopy(resolved))
    with pytest.raises(ValueError,match='NATIVE_FORMULA_CONDITIONAL_SCENARIO_INPUTS_REQUIRED'):
        native.NativeFormulaRequest.model_validate({
            **request,'conditional_definition_scenario':True,'scenario_inputs':{'p':{
                'contract_digest':context['contract_digest'],
                'origin':'caller_supplied_scenario','statement':'Already supplied',
                'assumptions':{},'context_values':{}}}})


def test_mcp_formula_tool_exposes_only_preview_request(monkeypatch):
    import asyncio
    from boi_wiki_mcp.app import v2
    assert hasattr(v2,'boi_native_formula'), 'MCP Formula tool is missing'
    async def api(path,payload):
        assert path=='/api/v2/domain-intake/formulas/preview'
        return {'status':'PROVISIONAL','request':payload,'equipment_execution':False}
    monkeypatch.setattr(v2,'v2_api_post',api)
    result=asyncio.run(v2.boi_native_formula({'formula':{'sentinel':'unchanged'}}))
    assert result['request']=={'formula':{'sentinel':'unchanged'}}
    assert result['equipment_execution'] is False


def test_explicit_compatible_observation_unit_keeps_parameter_and_boundary(monkeypatch):
    # A separately named scale is intentional: fix must not recognize Torr/Pa names.
    definitions=units()+[{'unit_id':'scaled_pressure','dimension':'pressure','scale':'250','offset':'0','revision':rev('e')}]
    at=invoke(monkeypatch,unit_definitions=definitions,observations=obs(4,unit='scaled_pressure'))
    above=invoke(monkeypatch,unit_definitions=definitions,observations=obs('4.001',unit='scaled_pressure'))
    assert at['evaluation']['value'] is True and above['evaluation']['value'] is False
    assert at['parameter_resolutions']['p']['parameter']['unit']=='pascal'
    assert any(u['unit_id']=='scaled_pressure' for u in at['observation_unit_definitions'])


def test_incompatible_or_unknown_observation_unit_still_rejected(monkeypatch):
    definitions=units()+[{'unit_id':'duration','dimension':'time','scale':'1','offset':'0','revision':rev('e')}]
    with pytest.raises(ValueError,match='FORMULA_OBSERVATION_UNIT_MISMATCH'):
        invoke(monkeypatch,unit_definitions=definitions,observations=obs(1,unit='duration'))
    with pytest.raises(ValueError,match='FORMULA_UNIT_NOT_FOUND'):
        invoke(monkeypatch,observations=obs(1,unit='not_declared'))


def test_converted_null_and_stale_observations_remain_unknown(monkeypatch):
    definitions=units()+[{'unit_id':'scaled_pressure','dimension':'pressure','scale':'250','offset':'0','revision':rev('e')}]
    for values in [obs(4,unit='scaled_pressure',value=None),obs(4,unit='scaled_pressure',observed_at='2026-09-08T09:59:00Z')]:
        assert invoke(monkeypatch,unit_definitions=definitions,observations=values)['evaluation']['status']=='unknown'


def test_formula_response_keeps_definition_evidence_separate_from_computed_value(monkeypatch):
    result = invoke(monkeypatch)
    resolution = result['parameter_resolutions']['p']
    assert resolution['definition_content']['observation']['unit_label'] == 'pascal'
    assert resolution['definition_content']['binding']['live_execution_ready'] is False
    assert result['evaluation']['value'] is True
    assert resolution['semantic_role_checked'] is False


def test_mcp_catalog_can_discover_without_namespace(monkeypatch):
    import asyncio
    from boi_wiki_mcp.app import v2
    from boi_api.app.v2.domain_intake import DomainAssetCatalogRequest
    async def api(path, payload):
        assert path == '/api/v2/domain-intake/assets/catalog'
        parsed = DomainAssetCatalogRequest.model_validate(payload)
        assert parsed.namespace is None
        return {'items': [], 'canonical_absence_proven': False}
    monkeypatch.setattr(v2, 'v2_api_post', api)
    result = asyncio.run(v2.boi_knowledge_catalog())
    assert result['canonical_absence_proven'] is False


def test_mcp_native_answer_uses_existing_authorized_delivery(monkeypatch):
    import asyncio
    from boi_wiki_mcp.app import v2
    async def api(path,payload):
        assert path=='/api/v2/domain-intake/native-results/answer'
        assert payload=={'revision':rev('a'),'lane':'provisional'}
        return {'question':'stored question','readable_text':'stored answer','current_request_fulfilled':None}
    monkeypatch.setattr(v2,'v2_api_post',api)
    assert asyncio.run(v2.boi_native_answer(rev('a')))['current_request_fulfilled'] is None


def test_mcp_formula_exposes_engine_schema_before_planning(monkeypatch):
    import asyncio
    from boi_wiki_mcp.app import v2
    from boi_api.app.v2.native_formula import NativeFormulaRequest
    async def api(path):
        assert path=='/api/v2/domain-intake/formulas/schema'
        return {'request_schema':NativeFormulaRequest.model_json_schema()}
    monkeypatch.setattr(v2,'v2_api_get',api)
    result=asyncio.run(v2.boi_native_formula())
    assert result['request_schema']==NativeFormulaRequest.model_json_schema()


def test_reviewed_unit_cannot_reuse_unrelated_definition_or_forge_scale(monkeypatch):
    from types import SimpleNamespace
    import json
    from boi_api.app.governed_runtime import native_definition_context
    from boi_api.app.v2.native_formula import read_native_unit_definition
    unit=units()[0]
    value={'contract_version':'boi/native-unit-interpretation@1',
        'unit_definition':{k:v for k,v in unit.items() if k!='revision'},
        'evidence':{'quote':'declared unit basis'}}
    authority=SimpleNamespace(definition_revisions=(rev('a'),),model_dump=lambda **kw:{'execution_authority_granted':False})
    # Revisions use the same typed object as the real review context.
    from boi_api.app.governed_runtime.semantic_binding_contract import RevisionRef
    authority.definition_revisions=(RevisionRef.model_validate(unit['revision']),)
    asset=SimpleNamespace(revision=authority.definition_revisions[0],content_json=json.dumps(value))
    monkeypatch.setattr(native_definition_context,'read_native_definition_authority',
        lambda *a,**k:(authority,SimpleNamespace(assets=(asset,))))
    result=read_native_unit_definition('work','auth',review_revision=rev('c'),unit=unit)
    assert result['unit_definition']['revision']==unit['revision']
    assert result['definition_content']['evidence']==value['evidence']
    with pytest.raises(ValueError,match='NATIVE_FORMULA_UNIT_DEFINITION_MISMATCH'):
        read_native_unit_definition('work','auth',review_revision=rev('c'),unit={**unit,'scale':'999'})
    value['contract_version']='boi/svid-native-interpretation@1';asset.content_json=json.dumps(value)
    with pytest.raises(ValueError,match='NATIVE_FORMULA_UNIT_CONTRACT_REQUIRED'):
        read_native_unit_definition('work','auth',review_revision=rev('c'),unit=unit)


def test_formula_consumes_requested_unit_review_before_execution(monkeypatch):
    from boi_api.app.v2 import native_formula
    calls=[]
    def read(work,authorization,*,review_revision,unit,require_current=True):
        calls.append(unit.unit_id)
        return {'unit_definition':unit.model_dump(mode='json'),'semantic_truth_proven':False}
    monkeypatch.setattr(native_formula,'read_native_unit_definition',read)
    result=invoke(monkeypatch,unit_definition_reviews={u['unit_id']:rev('c') for u in units()})
    assert calls==[u['unit_id'] for u in units()]
    assert result['unit_definition_authority']=='reviewed_candidate'
    assert result['evaluation']['value'] is True
    with pytest.raises(ValueError,match='NATIVE_FORMULA_UNIT_REVIEW_BINDINGS_MISMATCH'):
        invoke(monkeypatch,unit_definition_reviews={})
    def reject(*a,**kw):raise ValueError('NATIVE_FORMULA_UNIT_DEFINITION_MISMATCH')
    monkeypatch.setattr(native_formula,'read_native_unit_definition',reject)
    with pytest.raises(ValueError,match='NATIVE_FORMULA_UNIT_DEFINITION_MISMATCH'):
        invoke(monkeypatch,unit_definition_reviews={u['unit_id']:rev('c') for u in units()})


def test_server_formula_record_is_immutable_owned_and_read_without_reexecution(monkeypatch):
    from types import SimpleNamespace
    from boi_api.app.v2.store import MemoryAgentV2Store
    from boi_api.app.v2.native_formula import retain_formula_execution, read_formula_execution
    result=invoke(monkeypatch,observations={})
    request={'formula':formula(cmp()),'parameter_reviews':{'p':rev('c')},'unit_definitions':units(),
        'observations':{},'time_policy':{'now':'2026-09-08T10:00:05Z','max_age_seconds':10,'max_skew_seconds':None}}
    work=SimpleNamespace(store=MemoryAgentV2Store());auth=SimpleNamespace(principal='owner',policy_digest='policy')
    ref=retain_formula_execution(work,auth,request,result)
    assert retain_formula_execution(work,auth,request,result)==ref
    assert read_formula_execution(work,auth,ref)['result']['evaluation']['status']=='unknown'
    with pytest.raises(ValueError,match='NOT_ACCESSIBLE'):
        read_formula_execution(work,SimpleNamespace(principal='other',policy_digest='policy'),ref)
    with pytest.raises(ValueError,match='NOT_ACCESSIBLE'):
        read_formula_execution(work,SimpleNamespace(principal='owner',policy_digest='changed'),ref)
