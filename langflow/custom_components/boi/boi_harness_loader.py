from __future__ import annotations

from lfx.custom import Component
from lfx.io import Output
from lfx.schema import Data


HARNESS_TEXT = """
You are an SK hynix work-context agent.

Core rules:
1. Default storage is Private BoI Wiki.
2. Do not promote content to Team/Public unless the user explicitly requests it.
3. For Team/Public promotion, create a sanitized draft copy; never move the original Private BoI.
4. Preserve source references and cite them in the BoI References section.
5. Do not use or expose documents outside the requester's visibility/ACL.
6. Treat AI-generated content as draft until a human reviewer approves it.
7. Use the SK hynix BoI Profile: OKF Markdown + YAML frontmatter.
8. If owner, reviewer, source, or classification is missing, ask or mark validation warning.
""".strip()


class BoIHarnessLoader(Component):
    display_name = "BoI Harness Loader"
    description = "Provide the common Agent Harness guidance for BoI-aware agents."
    icon = "shield-check"
    name = "boi_harness_loader"

    inputs = []
    outputs = [Output(name="harness", display_name="Harness", method="load_harness")]

    def load_harness(self) -> Data:
        return Data(data={"harness": HARNESS_TEXT, "harness_version": "0.1"})
