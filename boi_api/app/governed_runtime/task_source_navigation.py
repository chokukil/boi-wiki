"""Existing optional workbook navigation; never defer semantic dependencies."""
import json


def defer_workbook_inventory(reader, parent, requirement):
    if requirement.role != 'source_inventory':
        return False
    owner = reader(parent)
    if owner.kind != 'definition':
        return False
    record = json.loads(owner.content_json).get('source_record')
    if not isinstance(record, dict) or not all(k in record for k in ('record_locator', 'field_refs', 'context_refs')):
        return False
    inventory = reader(requirement.revision)
    return (inventory.kind == 'source' and
            json.loads(inventory.content_json).get('contract_version') == 'boi/workbook-source-index@1')
