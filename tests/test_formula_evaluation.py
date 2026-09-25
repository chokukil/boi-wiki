"""Synthetic helper closure for focused MCP release validation."""
from tests.test_formula_preview import run,formula,cmp,lit,units,rev,compile_it


def obs(initial_value,**changes):
    o={'value':str(initial_value),'unit':'pascal','revision':rev('a'),'observed_at':'2026-09-08T10:00:04Z'}
    o.update(changes);return {'p':o}
