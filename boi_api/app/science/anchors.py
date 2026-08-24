"""Fail-closed Unicode source-span anchoring."""

from __future__ import annotations

from boi_api.app.science.digests import sha256_digest
from boi_api.app.science.models import SourceSpan


class SpanAnchorError(ValueError):
    """A source span cannot be attached uniquely to the supplied document."""


def _matches_at(text: str, span: SourceSpan, start: int) -> bool:
    end = start + len(span.exact)
    return (
        text[start:end] == span.exact
        and text[max(0, start - len(span.prefix)) : start] == span.prefix
        and text[end : end + len(span.suffix)] == span.suffix
    )


def resolve_anchor(
    text: str,
    span: SourceSpan,
    *,
    document_digest: str | None = None,
) -> SourceSpan:
    """Resolve an exact span by Unicode code-point offsets and unique context.

    ``document_digest`` is the canonical digest of the text supplied to this call.
    It is optional for callers that have not yet persisted a document identity, but
    when supplied it must match before any annotation can be attached.
    """

    if document_digest is not None and document_digest != sha256_digest(text):
        raise SpanAnchorError("anchor mismatch: document digest does not match")

    if span.end <= len(text) and _matches_at(text, span, span.start):
        return span.model_copy(deep=True)

    needle = f"{span.prefix}{span.exact}{span.suffix}"
    starts: list[int] = []
    cursor = 0
    while True:
        context_start = text.find(needle, cursor)
        if context_start < 0:
            break
        starts.append(context_start + len(span.prefix))
        cursor = context_start + 1

    if len(starts) != 1:
        raise SpanAnchorError(
            f"anchor mismatch: expected one contextual match, found {len(starts)}"
        )

    start = starts[0]
    return SourceSpan(
        offset_encoding="unicode_code_point",
        start=start,
        end=start + len(span.exact),
        exact=span.exact,
        prefix=span.prefix,
        suffix=span.suffix,
    )
