from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

from lfx.custom import Component
from lfx.io import Output, StrInput
from lfx.schema import Data


class BoIWikiReader(Component):
    display_name = "BoI Wiki Reader"
    description = "Read accessible Public, Team, and Web Private BoI documents for an employee."
    icon = "search"
    name = "boi_wiki_reader"

    inputs = [
        StrInput(name="query", display_name="Query", required=False),
        StrInput(name="employee_id", display_name="Employee ID", value="100001"),
        StrInput(name="boi_api_url", display_name="BoI API URL", value="http://boi-api:8000"),
    ]
    outputs = [Output(name="documents", display_name="Accessible BoI", method="read")]

    def _headers(self) -> dict[str, str]:
        token = os.getenv("BOI_API_SERVICE_TOKEN") or os.getenv("SERVICE_TOKEN") or ""
        return {"x-service-token": token} if token else {}

    def read(self) -> Data:
        params = urllib.parse.urlencode({"employee_id": self.employee_id, "q": self.query or ""})
        url = f"{self.boi_api_url.rstrip('/')}/api/boi?{params}"
        req = urllib.request.Request(url, headers=self._headers(), method="GET")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return Data(data=json.loads(resp.read().decode("utf-8")))
        except Exception as e:
            return Data(data={"ok": False, "error": repr(e)})
