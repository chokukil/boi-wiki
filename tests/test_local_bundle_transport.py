"""Synthetic helper closure for focused MCP release validation."""
def upload_url(value, object_id='source'):
    return '/api/v2/local-bundles/' + value['bundle_ref'].split(':')[-1] + '/objects/' + object_id + '?offset=0'
