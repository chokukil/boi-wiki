"""Syntactic link resolution only; never evidence entailment."""
from markdown_it import MarkdownIt


def rendered_links(text: str, *, reference_document: str | None = None) -> list[str]:
    parser = MarkdownIt('commonmark')
    environment = {}
    if reference_document is not None:
        parser.parse(reference_document, environment)
    links = []
    for block in parser.parse(text, environment):
        for token in block.children or []:
            if token.type == 'link_open':
                href = token.attrGet('href')
                if href and href not in links:
                    links.append(href)
    return links


def citation_links(text: str, *, reference_document: str | None = None) -> list[str]:
    """Resolve explicit numbered bibliography labels, not evidence entailment.

    A plain [n] is not clickable Markdown. It may nevertheless name a source
    explicitly listed as [n] followed by one link. Ambiguous labels stay unresolved.
    """
    import re
    links=rendered_links(text,reference_document=reference_document)
    if reference_document is None:return links
    parser=MarkdownIt('commonmark');mapping={}
    for block in parser.parse(reference_document):
        children=block.children or []
        opens=[i for i,t in enumerate(children) if t.type=='link_open']
        if len(opens)!=1:continue
        position=opens[0]
        prefix=''.join(t.content for t in children[:position] if t.type=='text')
        if any(t.type not in ('text','strong_open','strong_close','em_open','em_close') for t in children[:position]):continue
        match=re.fullmatch(r'\[(\d+)\]',prefix.strip())
        if match:
            mapping.setdefault(match.group(1),set()).add(children[position].attrGet('href'))
    for block in parser.parse(text):
        depth=0
        for token in block.children or []:
            if token.type=='link_open':depth+=1
            elif token.type=='link_close':depth-=1
            elif token.type=='text' and depth==0:
                for label in re.findall(r'(?<!\[)\[(\d+)\](?!\])',token.content):
                    candidates=mapping.get(label,set())
                    if len(candidates)==1:
                        url=next(iter(candidates))
                        if url and url not in links:links.append(url)
    return links


def rewrite_inline_link_destinations(text, replacements):
    """Rewrite parsed inline destinations only; unsupported source layouts stay exact."""
    from markdown_it.rules_inline import link
    parser=MarkdownIt('commonmark')
    edits=[]
    def capture(state, silent):
        start=state.pos;before=len(state.tokens)
        matched=link(state,silent)
        if matched and not silent:
            opens=[t for t in state.tokens[before:] if t.type=='link_open']
            if len(opens)==1:
                href=opens[0].attrGet('href');raw=state.src[start:state.pos]
                suffix=']('+href+')' if href else ''
                if href in replacements and suffix and raw.endswith(suffix):
                    edits.append((state.pos-len(href)-1,state.pos-1,replacements[href]))
        return matched
    parser.inline.ruler.at('link',capture)
    blocks=parser.parse(text)
    lines=text.splitlines(keepends=True);offsets=[0]
    for line in lines:offsets.append(offsets[-1]+len(line))
    changes=[]
    for block in blocks:
        if block.type!='inline' or block.map is None:continue
        lo,hi=offsets[block.map[0]],offsets[block.map[1]]
        region=text[lo:hi];content=block.content
        if not content or region.count(content)!=1:continue
        edits.clear();parser.inline.parse(content,parser,{},[])
        base=lo+region.index(content)
        changes.extend((base+a,base+b,value) for a,b,value in edits)
    for a,b,value in sorted(set(changes),reverse=True):text=text[:a]+value+text[b:]
    return text
