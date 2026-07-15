from __future__ import annotations

import ast
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGETS = (
    ROOT / "boi_api/app/v2/quick_agent.py",
    ROOT / "boi_api/app/v2/semantic_kernel.py",
    ROOT / "boi_api/app/v2/entity_resolver.py",
    ROOT / "boi_api/app/v2/service.py",
    ROOT / "boi_api/app/v2/work_learning.py",
    ROOT / "boi_api/app/v2/worker.py",
)
MODEL_LIFECYCLE_EXEMPTIONS = {ROOT / "boi_api/app/v2/openkb_compat.py"}
MODEL_LIFECYCLE_ENDPOINTS = (
    "/api/v1/models/load",
    "/api/v1/models/unload",
    "/models/load",
    "/models/unload",
)
SERVICE_SCOPES = {"_semantic_route", "_create_goal_plan", "_run_turn"}
CATALOG_ONLY_SCOPES = {"starter_suggestions"}
CAPABILITY_ID_LITERAL = re.compile(r"^[a-z][a-z0-9_-]*(?:\.[a-z0-9_-]+)+$")
SEMANTIC_NAMES = {
    "question",
    "goal",
    "title",
    "prompt",
    "resolved_goal",
    "retrieval_query",
    "topic_subject",
    "mention",
}
SEMANTIC_METHODS = {
    "casefold",
    "endswith",
    "find",
    "index",
    "lower",
    "partition",
    "removeprefix",
    "removesuffix",
    "replace",
    "rfind",
    "rpartition",
    "rsplit",
    "split",
    "startswith",
    "upper",
}
REGEX_METHODS = {"compile", "findall", "finditer", "fullmatch", "match", "search", "split", "sub"}
MUTATING_METHODS = {
    "append", "clear", "extend", "insert", "pop", "remove", "reverse", "setdefault", "sort", "update"
}


def _names(node: ast.AST) -> set[str]:
    return {item.id for item in ast.walk(node) if isinstance(item, ast.Name)}


def _attribute_root(node: ast.AST) -> str:
    current = node
    while isinstance(current, ast.Attribute):
        current = current.value
    return current.id if isinstance(current, ast.Name) else ""


def _string_literals(node: ast.AST) -> list[str]:
    return [
        item.value
        for item in ast.walk(node)
        if isinstance(item, ast.Constant) and isinstance(item.value, str)
    ]


class SemanticArchitectureVisitor(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.scope: list[str] = []
        self.class_scope: list[str] = []
        self.errors: list[str] = []

    def _report(self, node: ast.AST, message: str) -> None:
        self.errors.append(f"{self.path.relative_to(ROOT)}:{getattr(node, 'lineno', 0)}: {message}")

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.class_scope.append(node.name)
        self.generic_visit(node)
        self.class_scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Call(self, node: ast.Call) -> None:
        semantic_scope = self.path.name != "service.py" or (self.scope and self.scope[-1] in SERVICE_SCOPES)
        if semantic_scope and isinstance(node.func, ast.Attribute):
            method = node.func.attr
            receiver_names = _names(node.func.value)
            if method in SEMANTIC_METHODS and receiver_names & SEMANTIC_NAMES:
                self._report(node, f"semantic text routing via .{method}() is forbidden")
            if _attribute_root(node.func) == "re" and method in REGEX_METHODS:
                argument_names = set().union(*(_names(item) for item in node.args)) if node.args else set()
                if argument_names & SEMANTIC_NAMES:
                    self._report(node, f"regex semantic routing via re.{method}() is forbidden")
            if (
                self.class_scope
                and self.class_scope[-1] == "PlanValidator"
                and method in MUTATING_METHODS
                and "plan" in receiver_names
            ):
                self._report(node, "PlanValidator must not mutate SemanticPlan collections")
        if (
            self.class_scope
            and self.class_scope[-1] == "PlanValidator"
            and isinstance(node.func, ast.Name)
            and node.func.id == "setattr"
            and node.args
            and "plan" in _names(node.args[0])
        ):
            self._report(node, "PlanValidator must not mutate SemanticPlan with setattr")
        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> None:
        semantic_scope = self.path.name != "service.py" or (self.scope and self.scope[-1] in SERVICE_SCOPES)
        if semantic_scope and _names(node) & SEMANTIC_NAMES and _string_literals(node):
            self._report(node, "semantic text comparison against string literals is forbidden")
        if self.path.name == "service.py" and self.scope and self.scope[-1] in SERVICE_SCOPES:
            if any(
                isinstance(item, ast.Attribute) and item.attr == "handler"
                for item in ast.walk(node)
            ) and _string_literals(node):
                self._report(node, "capability handlers must be dispatched through CapabilityHandlerRegistry")
            literals = _string_literals(node)
            capability_literals = [item for item in literals if "." in item and not item.startswith("_")]
            if capability_literals and "capability" in " ".join(_names(node)):
                self._report(node, "capability-id semantic branching is forbidden in the turn route")
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if (
            self.path.name == "service.py"
            and self.scope
            and self.scope[-1] in CATALOG_ONLY_SCOPES
            and isinstance(node.value, str)
            and CAPABILITY_ID_LITERAL.fullmatch(node.value)
        ):
            self._report(node, "capability IDs in starter generation must come from the catalog")
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        if self.class_scope and self.class_scope[-1] == "PlanValidator":
            for target in node.targets:
                if isinstance(target, ast.Attribute) and _attribute_root(target) == "plan":
                    self._report(node, "PlanValidator must not mutate SemanticPlan")
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        if (
            self.class_scope
            and self.class_scope[-1] == "PlanValidator"
            and isinstance(node.target, ast.Attribute)
            and _attribute_root(node.target) == "plan"
        ):
            self._report(node, "PlanValidator must not mutate SemanticPlan")
        self.generic_visit(node)


def check(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
    errors: list[str] = []
    if "safe_search" in source:
        errors.append(f"{path.relative_to(ROOT)}: safe_search fallback is forbidden")
    if path.name == "worker.py":
        forbidden_tool_loop_markers = {
            "seen_calls": "tool progress must be based on domain-state deltas, not call strings",
            "no_progress_repeated_search": "search wording must not decide loop progress",
            "no_progress_repeated_evidence_read": "evidence-id call strings must not decide loop progress",
        }
        for marker, message in forbidden_tool_loop_markers.items():
            if marker in source:
                errors.append(f"{path.relative_to(ROOT)}: {message}: {marker}")
    if path.name == "work_learning.py":
        forbidden_harness_markers = {
            'harness_id == "learning.capture"': "Harness phases must come from HarnessDefinition",
            'harness_id != "context.work"': "Harness phases must come from HarnessDefinition",
        }
        for marker, message in forbidden_harness_markers.items():
            if marker in source:
                errors.append(f"{path.relative_to(ROOT)}: {message}: {marker}")
        progress_function = re.search(
            r"def _progress_signature\(.*?\n(?=\n(?:class|def) )",
            source,
            flags=re.DOTALL,
        )
        if progress_function and '"strategy":' in progress_function.group(0):
            errors.append(
                f"{path.relative_to(ROOT)}: free-text strategy must not contribute to progress signatures"
            )
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name != "resolve_loop_policy":
                continue
            semantic_attributes = {
                item.attr
                for item in ast.walk(node)
                if isinstance(item, ast.Attribute)
                and item.attr in {"asset_kind", "operation", "goal", "resolved_goal"}
            }
            if semantic_attributes:
                errors.append(
                    f"{path.relative_to(ROOT)}:{node.lineno}: loop contracts must come from SemanticPlan/catalog; "
                    f"runtime semantic inference found: {', '.join(sorted(semantic_attributes))}"
                )
    visitor = SemanticArchitectureVisitor(path)
    visitor.visit(ast.parse(source, filename=str(path)))
    errors.extend(visitor.errors)
    return errors


def main() -> int:
    errors = [error for path in TARGETS for error in check(path)]
    for path in (ROOT / "boi_api/app").rglob("*.py"):
        if path in MODEL_LIFECYCLE_EXEMPTIONS:
            continue
        source = path.read_text(encoding="utf-8")
        for endpoint in MODEL_LIFECYCLE_ENDPOINTS:
            if endpoint in source:
                errors.append(
                    f"{path.relative_to(ROOT)}: LM Studio lifecycle endpoint is forbidden: {endpoint}"
                )
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("semantic kernel architecture checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
