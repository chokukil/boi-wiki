"""Synthetic helper closure for focused MCP release validation."""
import importlib.util


from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


KIT = ROOT / 'agent_kit'


def load_installer(path=KIT / 'install.py'):
    spec = importlib.util.spec_from_file_location('boi_portable_installer', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
