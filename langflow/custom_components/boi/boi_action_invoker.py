from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from lfx.custom import Component
from lfx.io import BoolInput, DataInput, Output, StrInput
from lfx.schema import Data


class BoIActionInvoker(Component):
    display_name = "BoI Action Invoker"
    description = "Invoke an allow-listed API/Webhook Action through the BoI Action Gateway. Use dry-run by default for safe PoC execution."
    icon = "plug"
    name = "boi_action_invoker"

    inputs = [
        StrInput(name="action_key", display_name="Action Key", value="sop.equipment.request_raw_data"),
        DataInput(name="payload", display_name="Payload", required=False),
        DataInput(name="event", display_name="Event", required=False),
        StrInput(name="boi_id", display_name="BoI ID", value="", required=False),
        StrInput(name="employee_id", display_name="Employee ID", value="100001"),
        BoolInput(name="dry_run", display_name="Dry Run", value=True),
        StrInput(name="approved_by", display_name="Approved By", value="", required=False),
        StrInput(name="action_gateway_url", display_name="Action Gateway URL", value="http://action-gateway:8100"),
        StrInput(name="service_token", display_name="Service Token", value="dev-service-token-change-me"),
    ]
    outputs = [Output(name="result", display_name="Action Result", method="invoke")]

    def _as_dict(self, value: Any) -> dict[str, Any]:
        if not value:
            return {}
        if hasattr(value, "data"):
            return value.data or {}
        if isinstance(value, dict):
            return value
        return {}

    def invoke(self) -> Data:
        request_body = {
            "action_key": self.action_key,
            "employee_id": self.employee_id,
            "event": self._as_dict(self.event),
            "boi_id": self.boi_id or None,
            "payload": self._as_dict(self.payload),
            "dry_run": bool(self.dry_run),
            "approved_by": self.approved_by or None,
        }
        payload = json.dumps(request_body, ensure_ascii=False).encode("utf-8")
        url = f"{self.action_gateway_url.rstrip('/')}/api/actions/invoke"
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json", "x-service-token": self.service_token},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return Data(data=json.loads(resp.read().decode("utf-8")))
        except urllib.error.HTTPError as e:
            return Data(data={"ok": False, "status": e.code, "error": e.read().decode("utf-8")})
        except Exception as e:
            return Data(data={"ok": False, "error": repr(e)})
