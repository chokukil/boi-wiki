"""Human Wiki links from explicit deployment configuration, never request hosts.

These are presentation links only. They neither read sources nor grant access.
"""
from dataclasses import dataclass
from ipaddress import IPv6Address
import os
import re
from urllib.parse import urlsplit


@dataclass(frozen=True)
class PublicWikiLinks:
    origin: str | None
    status: str

    @classmethod
    def from_config(cls, value: str | None):
        if value is None or value == '':
            return cls(None, 'not_configured')
        # urlsplit strips some control characters; reject them before parsing.
        if (not isinstance(value, str) or len(value) > 2048
                or any(c.isspace() or ord(c) <= 32 or ord(c) == 127 for c in value)
                or any(c in value for c in ('\\', '?', '#', '@'))):
            return cls(None, 'invalid_configuration')
        try:
            parsed = urlsplit(value)
            host, port = parsed.hostname, parsed.port
            if (parsed.scheme not in ('http', 'https') or not host
                    or parsed.path not in ('', '/') or parsed.netloc.endswith(':')
                    or (port is not None and not 1 <= port <= 65535)):
                raise ValueError
            if ':' in host:
                if not re.fullmatch(r'\[[0-9a-fA-F:.]+\](?::[0-9]+)?', parsed.netloc):
                    raise ValueError
                host = '[' + str(IPv6Address(host)) + ']'
            else:
                host = host.encode('idna').decode('ascii').lower()
                labels = host.removesuffix('.').split('.')
                if len(host) > 253 or any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label)
                                          for label in labels):
                    raise ValueError
            origin = parsed.scheme + '://' + host + (':' + str(port) if port is not None else '')
            return cls(origin, 'configured')
        except (ValueError, UnicodeError):
            # Do not reflect a malformed configuration (possibly credentials).
            return cls(None, 'invalid_configuration')

    def url(self, path: str) -> str:
        # Only explicit server-generated routes are decorated, not source URLs.
        if (not path.startswith('/') or path.startswith('//') or '\\' in path
                or any(c.isspace() or ord(c) <= 32 or ord(c) == 127 for c in path)):
            raise ValueError('PUBLIC_WIKI_PATH_INVALID')
        return (self.origin or '') + path

    def metadata(self) -> dict:
        return {'contract_version': 'boi/public-wiki-links@1', 'status': self.status,
                'origin': self.origin,
                'link_scope': 'configured_public_origin' if self.origin else 'relative_product_route'}


def configured_public_links() -> PublicWikiLinks:
    """Read the existing human Wiki setting, with no internal or Host fallback."""
    return PublicWikiLinks.from_config(os.environ.get('BOI_EXTERNAL_URL'))
