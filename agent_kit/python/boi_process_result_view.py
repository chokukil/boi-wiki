"""Compatibility export for local evidence files; product rendering is shared."""
from pathlib import Path
from boi_api.app.v2.process_result_view import process_result_html
from boi_api.app.v2.process_citation_display import citation_display

def render_process_result(packet, path, *, questions=(), sources=()):
    display=citation_display(packet,sources) if sources else None
    Path(path).write_text(process_result_html(packet,questions=questions,sources=sources,citation_display=display),encoding="utf-8")
