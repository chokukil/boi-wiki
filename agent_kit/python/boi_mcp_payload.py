"""Decode MCP result envelopes; never infer business meaning from payload text."""
import json


def mcp_result_values(result, *, depth=0):
    if depth>4:
        raise ValueError('MCP_RESULT_ENVELOPE_DEPTH')
    if not isinstance(result,dict) or result.get('isError'):
        return []
    structured=[result[k] for k in ('structuredContent','structured_content') if isinstance(result.get(k),dict)]
    if structured:
        if any(value!=structured[0] for value in structured[1:]):
            raise ValueError('MCP_RESULT_STRUCTURED_CONFLICT')
        return [structured[0]]
    values=[]
    for block in result.get('content',[]):
        if not isinstance(block,dict) or block.get('type')!='text':continue
        try:value=json.loads(block.get('text',''))
        except (ValueError,TypeError):continue
        if not isinstance(value,dict):continue
        if ('contract_version' not in value and isinstance(value.get('content'),list)
                and any(k in value for k in ('structuredContent','structured_content','isError'))):
            values.extend(mcp_result_values(value,depth=depth+1))
        else:values.append(value)
    return values
