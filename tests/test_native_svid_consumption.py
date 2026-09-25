"""Synthetic helper closure for focused MCP release validation."""
import json


from types import SimpleNamespace


from tests.test_svid_parameter_catalog import row,request


from boi_api.app.governed_runtime.semantic_binding_contract import RevisionRef


def installed(monkeypatch, *, unsupported=False, live=False, semantic_descriptor=None, source_meaning=None):
    from boi_api.app.governed_runtime import native_definition_context
    rev=RevisionRef.model_validate(row()['revision'])
    value={'contract_version':'unknown' if unsupported else 'boi/svid-native-interpretation@1',
        'identity':{'namespace':'plant-x','model':{'value':'M1'},'svid':{'value':'9'}},
        'parameter':{'name':'P'},'observation':{'component':'zone-a','quantity':'pressure','unit_label':'pascal'},
        'location':{'source_locator':'source/zone-a','live_binding_verified':live},
        'binding':{'status':'unverified','live_execution_ready':False},'canonical_projection_eligible':False,
        'limitations':['transcript only']}
    if semantic_descriptor is not None:value['semantic_descriptor']=semantic_descriptor
    if source_meaning is not None:value.update(source_meaning)
    authority=SimpleNamespace(definition_revisions=(rev,),definition_context_digest='sha256:'+'c'*64,
        model_dump=lambda **kwargs:{'reviewer_relationship':'same_session','execution_authority_granted':False})
    asset=SimpleNamespace(revision=rev,kind='definition',content_json=json.dumps(value))
    calls=[]
    def read(work,auth,review,*,definition_use,require_current=True):
        assert '/observation' in definition_use['target_pointers']
        assert definition_use['optional_target_pointers']==('/semantic_descriptor',)
        calls.append((work,auth,review));return authority,SimpleNamespace(assets=(asset,))
    monkeypatch.setattr(native_definition_context,'read_native_definition_authority',read)
    return calls
