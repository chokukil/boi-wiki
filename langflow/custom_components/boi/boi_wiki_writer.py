from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from lfx.custom import Component
from lfx.io import DataInput, MessageInput, MultilineInput, Output, StrInput
from lfx.schema import Data


class BoIWikiWriter(Component):
    display_name = "BoI Wiki Writer"
    description = "Write a BoI document to the Web BoI Wiki API."
    icon = "database"
    name = "boi_wiki_writer"

    inputs = [
        DataInput(name="metadata", display_name="Metadata"),
        MessageInput(name="body_message", display_name="Body Message", required=False),
        MultilineInput(name="body", display_name="Body"),
        StrInput(name="boi_api_url", display_name="BoI API URL", value="http://boi-api:8000"),
        StrInput(name="employee_id", display_name="Employee ID", value="100001"),
    ]
    outputs = [Output(name="result", display_name="Write Result", method="write")]

    def write(self) -> Data:
        meta: dict[str, Any] = self.metadata.data if hasattr(self.metadata, "data") else dict(self.metadata)
        body = self.body or (getattr(self.body_message, "text", "") if self.body_message else "")
        payload = json.dumps({"metadata": meta, "body": body}, ensure_ascii=False).encode("utf-8")
        url = f"{self.boi_api_url.rstrip('/')}/api/boi?employee_id={self.employee_id}"
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return Data(data=json.loads(resp.read().decode("utf-8")))
        except urllib.error.HTTPError as e:
            return Data(data={"ok": False, "status": e.code, "error": e.read().decode("utf-8")})
        except Exception as e:
            return Data(data={"ok": False, "error": repr(e)})
