from __future__ import annotations

import re
from html import escape
from urllib.parse import urlsplit


_INLINE_CODE = re.compile(r"`([^`\n]+)`")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")


def _safe_href(value: str) -> str:
    href = str(value or "").strip()
    parsed = urlsplit(href)
    if href.startswith("/") and not href.startswith("//"):
        return escape(href, quote=True)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return escape(href, quote=True)
    return ""


def _inline(value: str) -> str:
    tokens: list[str] = []

    def code_token(match: re.Match[str]) -> str:
        tokens.append(f"<code>{escape(match.group(1))}</code>")
        return f"@@CODE_{len(tokens) - 1}@@"

    source = _INLINE_CODE.sub(code_token, str(value or ""))
    rendered = escape(source)

    def link(match: re.Match[str]) -> str:
        href = _safe_href(match.group(2))
        label = escape(match.group(1))
        return f'<a href="{href}">{label}</a>' if href else label

    rendered = _LINK.sub(link, rendered)
    rendered = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", rendered)
    rendered = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", rendered)
    for index, token in enumerate(tokens):
        rendered = rendered.replace(f"@@CODE_{index}@@", token)
    return rendered


def render_agent_markdown(value: str) -> str:
    """Render the small, safe Markdown subset used by Agent answers.

    Raw HTML is always escaped. Links are limited to local routes and explicit
    HTTP(S) references, so LLM output cannot introduce scriptable markup.
    """

    lines = str(value or "").splitlines()
    output: list[str] = []
    paragraph: list[str] = []
    unordered: list[str] = []
    ordered: list[str] = []
    quote: list[str] = []
    index = 0

    def flush() -> None:
        if paragraph:
            output.append(f"<p>{_inline(' '.join(item.strip() for item in paragraph))}</p>")
            paragraph.clear()
        if unordered:
            output.append("<ul>" + "".join(f"<li>{_inline(item)}</li>" for item in unordered) + "</ul>")
            unordered.clear()
        if ordered:
            output.append("<ol>" + "".join(f"<li>{_inline(item)}</li>" for item in ordered) + "</ol>")
            ordered.clear()
        if quote:
            output.append(f"<blockquote>{_inline(' '.join(quote))}</blockquote>")
            quote.clear()

    while index < len(lines):
        raw = lines[index]
        stripped = raw.strip()
        if stripped.startswith("```"):
            flush()
            language = stripped[3:].strip().split(None, 1)[0] if stripped[3:].strip() else ""
            code: list[str] = []
            index += 1
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code.append(lines[index])
                index += 1
            output.append(
                f'<pre class="code-block"><code data-language="{escape(language, quote=True)}">'
                f"{escape(chr(10).join(code))}</code></pre>"
            )
        elif not stripped:
            flush()
        elif re.fullmatch(r"#{1,4}\s+.+", stripped):
            flush()
            marker, title = stripped.split(" ", 1)
            level = min(5, len(marker) + 2)
            output.append(f"<h{level}>{_inline(title)}</h{level}>")
        elif re.match(r"^[-*+]\s+\S", stripped):
            if paragraph or ordered or quote:
                flush()
            unordered.append(re.sub(r"^[-*+]\s+", "", stripped))
        elif re.match(r"^\d+\.\s+\S", stripped):
            if paragraph or unordered or quote:
                flush()
            ordered.append(re.sub(r"^\d+\.\s+", "", stripped))
        elif stripped.startswith(">"):
            if paragraph or unordered or ordered:
                flush()
            quote.append(stripped.lstrip("> "))
        elif re.fullmatch(r"(?:-{3,}|_{3,}|\*{3,})", stripped):
            flush()
            output.append("<hr>")
        else:
            if unordered or ordered or quote:
                flush()
            paragraph.append(raw)
        index += 1

    flush()
    return '<div class="agent-answer-markdown">' + "".join(output) + "</div>"
