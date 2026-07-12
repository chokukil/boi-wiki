"""BoI Agent v2.

The v2 package is intentionally isolated from the legacy Agent implementation in
``app.main``.  The main application only mounts the router built here.
"""

from .routes import build_agent_v2_router
from .domain import DomainServiceGateway
from .service import AgentV2Service, build_agent_v2_service

__all__ = ["AgentV2Service", "DomainServiceGateway", "build_agent_v2_router", "build_agent_v2_service"]
