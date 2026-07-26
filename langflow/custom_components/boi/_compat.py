from __future__ import annotations

try:
    from lfx.custom.custom_component.component import Component
    from lfx.io import BoolInput, DataInput, DropdownInput, IntInput, MessageInput, MultilineInput, Output, StrInput
    from lfx.schema import Data
    from lfx.schema.message import Message
except ModuleNotFoundError:
    from langflow.custom import Component
    from langflow.io import BoolInput, DataInput, DropdownInput, IntInput, MessageInput, MultilineInput, Output, StrInput
    from langflow.schema import Data
    from langflow.schema.message import Message

__all__ = [
    "BoolInput",
    "Component",
    "Data",
    "DataInput",
    "DropdownInput",
    "IntInput",
    "Message",
    "MessageInput",
    "MultilineInput",
    "Output",
    "StrInput",
]
