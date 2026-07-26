"""Validation-only Agent Hub component with an incompatible Agent-slot contract.

The component is deliberately valid Python and deployable by Agent Hub, but its
input/output contract does not match ``boi.agent-slot.v1``.  It proves that the
Playground refuses to auto-wire an ambiguous or incompatible shared component.
"""

from __future__ import annotations

from langflow.custom import Component
from langflow.io import DataInput, Output
from langflow.schema import Data


class IncompatibleAgentSlot(Component):
    component_contract = {
        "schema_version": "boi.agent-slot.v2",
        "inputs": ["raw_prompt"],
        "outputs": ["raw_result"],
    }
    display_name = "Incompatible Agent Slot"
    description = "Validation fixture that must require manual composition."
    icon = "TriangleAlert"
    name = "IncompatibleAgentSlot"

    inputs = [
        DataInput(
            name="raw_prompt",
            display_name="Raw Prompt",
            required=True,
        ),
    ]
    outputs = [
        Output(
            name="raw_result",
            display_name="Raw Result",
            method="build_raw_result",
        ),
    ]

    def build_raw_result(self) -> Data:
        source = self.raw_prompt
        if isinstance(source, Data):
            return source
        if isinstance(source, dict):
            return Data(data=source)
        return Data(data={"value": str(source or "")})
