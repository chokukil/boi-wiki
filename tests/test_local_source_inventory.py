"""Synthetic helper closure for focused MCP release validation."""
from boi_api.app.governed_runtime.source_envelope import byte_digest


def layout(raw):
    return {'source_digest': byte_digest(raw), 'interpretation_basis': 'Explicit source inspection',
            'regions': [
                {'sheet': 'raw', 'first_row': 1, 'last_row': 1, 'columns': ['A', 'B'],
                 'role': 'metadata', 'reason': 'Header cells'},
                {'sheet': 'raw', 'first_row': 2, 'last_row': 2, 'columns': ['A', 'C'],
                 'role': 'source', 'reason': 'Declared raw readings'},
                {'sheet': 'raw', 'first_row': 2, 'last_row': 2, 'columns': ['B'],
                 'role': 'provided_model_answer', 'reason': 'Provided response, not evidence'},
            ]}
