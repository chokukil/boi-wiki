"""Synthetic helper closure for focused MCP release validation."""
from dataclasses import replace


from boi_api.app.governed_runtime.source_field_projection import SourceFieldProjectionService, project_fields


from tests.test_governed_source_intake import setup, inline


def captured(tmp_path, raw, media='application/json'):
    source, auth = setup(tmp_path)
    auth = replace(auth, allowed_uses=(*auth.allowed_uses, 'model_input'))
    reference = source.capture(authorization=auth, envelope={**inline(raw), 'media_type':media}, idempotency_key='raw')
    return source, auth, reference, SourceFieldProjectionService(source)
