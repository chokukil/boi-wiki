"""Synthetic helper closure for focused MCP release validation."""
import base64


from datetime import datetime,timezone


from boi_api.app.v2.store import MemoryAgentV2Store


from boi_api.app.governed_runtime.ledger import GovernedRuntimeLedger,RecordKind


from boi_api.app.governed_runtime.release_rebuild import KnowledgeObjectStore


from boi_api.app.governed_runtime.source_intake import SourceIntakeService,IntakeAuthorization,ConnectorSnapshot


def setup(tmp_path):
    store=MemoryAgentV2Store();ledger=GovernedRuntimeLedger(tmp_path/'ledger')
    objects=KnowledgeObjectStore(tmp_path/'objects')
    auth=IntakeAuthorization('owner','sha256:'+'a'*64,('store','derive'))
    service=SourceIntakeService(store=store,ledger=ledger,objects=objects,
        clock=lambda:datetime(2026,9,4,tzinfo=timezone.utc))
    return service,auth


def inline(raw=b'{"metadata":"descriptive only"}'):
    return {'kind':'inline_source','role':'corporate_metadata','media_type':'application/json',
            'content_b64':base64.b64encode(raw).decode()}
