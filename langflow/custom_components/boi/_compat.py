from __future__ import annotations

try:
    from lfx.custom.custom_component.component import Component
    from lfx.io import BoolInput, DataInput, DropdownInput, MultilineInput, Output, StrInput
    from lfx.schema import Data
except ModuleNotFoundError:
    from langflow.custom import Component
    from langflow.io import BoolInput, DataInput, DropdownInput, MultilineInput, Output, StrInput
    from langflow.schema import Data

__all__ = [
    "BoolInput",
    "Component",
    "Data",
    "DataInput",
    "DropdownInput",
    "MultilineInput",
    "Output",
    "StrInput",
]
