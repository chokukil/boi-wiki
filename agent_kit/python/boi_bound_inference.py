"""Assemble caller-read execution metadata before normal Wiki admission.

No semantic repair, post-signature mutation, receipt creation or new authority.
The caller supplies exact read-context values; Wiki independently checks them.
"""
import copy,json
from pathlib import Path
from jsonschema import validate
from boi_api.app.governed_runtime.semantic_binding_contract import semantic_digest
from .boi_structured_provider import strict_output_schema


def _parts(pointer):
    if not pointer.startswith('/') or not pointer[1:]:raise ValueError('METADATA_BINDING_POINTER_INVALID')
    return [p.replace('~1','/').replace('~0','~') for p in pointer[1:].split('/')]


def semantic_output_schema(schema,bindings):
    """Omit explicit scalar object fields only, not inferred semantic fields."""
    result=strict_output_schema(schema)
    def expand(node):
        if '$ref' in node:
            ref=node.pop('$ref')
            if not ref.startswith('#/$defs/'):raise ValueError('METADATA_BINDING_REF_UNSUPPORTED')
            original=copy.deepcopy(result['$defs'][ref[len('#/$defs/'):]])
            original.update(node);node.clear();node.update(original)
        return node
    for pointer,value in bindings.items():
        node=result;parts=_parts(pointer)
        for part in parts[:-1]:node=expand(node)['properties'][part]
        properties=expand(node)['properties'];field=properties[parts[-1]]
        if field.get('type') not in ('string','integer','number','boolean','null'):
            raise ValueError('METADATA_BINDING_SCALAR_REQUIRED')
        validate(value,{'$defs':result.get('$defs',{}),**field})
        del properties[parts[-1]]
        node['required']=[p for p in node.get('required',[]) if p!=parts[-1]]
    # Remove unreferenced definitions after inlining: never show the model a
    # second, obsolete form of the same output object.
    definitions=result.get('$defs',{});needed=set()
    def refs(value):
        if isinstance(value,dict):
            ref=value.get('$ref','')
            if ref.startswith('#/$defs/') and ref[8:] not in needed:
                needed.add(ref[8:]);refs(definitions[ref[8:]])
            for k,v in value.items():
                if k!='$defs':refs(v)
        elif isinstance(value,list):
            for v in value:refs(v)
    refs(result)
    if '$defs' in result:result['$defs']={k:v for k,v in definitions.items() if k in needed}
    return result


def infer_with_bound_metadata(*,infer,bindings,schema,prompt,output_dir,**kwargs):
    """Preserve provider raw output and separately journal the assembled value."""
    bindings=copy.deepcopy(bindings)
    projected=semantic_output_schema(schema,bindings)
    root=Path(output_dir)
    if root.exists():raise FileExistsError(root)
    binding={'contract_version':'boi/external-metadata-binding@1','bindings':bindings,
        'knowledge_reading_ref':kwargs.get('knowledge_reading_ref'),
        'input_revisions':kwargs.get('input_revisions'),
        'full_schema_digest':semantic_digest(schema),'semantic_schema_digest':semantic_digest(projected),
        'authority_created':False,'status':'awaiting_provider'}
    try:
        raw,run=infer(prompt=prompt+'\nHost-bound metadata fields are omitted from the output schema. '
            'Do not generate those fields. Return only the requested semantic object; '
            'the external caller will bind exact read-context values before Wiki validation.',
            schema=projected,output_dir=root,**kwargs)
        binding['semantic_output_digest']=semantic_digest(raw)
        validate(raw,projected)
        value=copy.deepcopy(raw)
        for pointer,datum in bindings.items():
            parent=value;parts=_parts(pointer)
            for part in parts[:-1]:parent=parent[part]
            if parts[-1] in parent:raise ValueError('METADATA_BINDING_OVERRIDE_REFUSED')
            parent[parts[-1]]=datum
        validate(value,schema)
        binding.update(status='assembled_pending_wiki_validation',assembled_digest=semantic_digest(value))
        (root/'assembled-output.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
        return value,{**run,'metadata_binding':binding,'assembled_output_path':str(root/'assembled-output.json')}
    except Exception as exc:
        binding.update(status='failed',error_type=type(exc).__name__)
        raise
    finally:
        # The provider owns creation of its exclusive output directory.
        if root.is_dir():
            (root/'metadata-binding.json').write_text(json.dumps(binding,ensure_ascii=False,indent=2)+'\n')
