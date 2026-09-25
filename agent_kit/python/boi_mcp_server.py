"""Official SDK 2 server defaults for explicitly invoked external kit hosts."""
from mcp.server.mcpserver import MCPServer


class BoiLocalMCPServer(MCPServer):
    def streamable_http_app(self, **kwargs):
        return super().streamable_http_app(**{'streamable_http_path':'/mcp','stateless_http':True,**kwargs})
