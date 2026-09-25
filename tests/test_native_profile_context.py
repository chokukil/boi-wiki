"""Synthetic helper closure for focused MCP release validation."""
import json


from boi_api.app.governed_runtime.native_profile_context import NativeProfileEntry, NativeProfileProjection, build_native_profile_bundle


from tests.test_native_definition_authority import binding


from boi_api.app.governed_runtime.native_definition_context import read_native_definition_authority


from boi_api.app.governed_runtime.semantic_query_execution import capture_sqlite_planner_catalog


def material(tmp_path):
    work, auth, review, definition = binding(tmp_path/'assets')
    authority, context = read_native_definition_authority(work, auth, review)
    path=tmp_path/'source.sqlite'
    import sqlite3
    con=sqlite3.connect(path); con.execute('CREATE TABLE sample (id TEXT)'); con.commit(); con.close(); table='sample'
    catalog=capture_sqlite_planner_catalog(path,source_id='local',allowed_tables=(table,),captured_at='2026-09-08T00:00:00Z')
    projection=NativeProfileProjection(definition_review_revision=review,
        definition_revisions=[definition],catalog_snapshot_digest=catalog.snapshot_digest,
        schema_digest=catalog.schema_digest,entries=[NativeProfileEntry(entry_id='object:sample',
            category='domain',definition_revision=definition,
            payload_json=json.dumps({'id':'object:sample','kind':'ObjectType','definition':'Synthetic test object'}))])
    return authority,context,catalog,projection
