"""Carry a bounded server recipient selector and apply its current read result."""
import copy
from agent_kit.python.boi_recipient_citations import recipient_access, access_notice
from agent_kit.python.boi_markdown_links import rendered_links


async def recipient_projection(value, *, recipient, api_post, published=False):
    if recipient is None:
        return value
    out=copy.deepcopy(value)
    answers=out.get("answers",[out])
    urls=[]
    if published:
        from .published_citations import with_published_citations
        out=with_published_citations(out)
        urls=[r["url"] for r in out.get("citation_presentation",{}).get("references",[])]
        if out.get("document_url"):urls.append(out["document_url"])
    else:
        for answer in answers:
            urls.extend(rendered_links(answer.get("readable_text","")))
    urls=list(dict.fromkeys(urls))
    if not urls:return out
    # One bounded server evaluation; never infer other URLs from a passing one.
    results={};identity=None
    for offset in range(0,len(urls),64):
        batch=urls[offset:offset+64]
        try:
            response=await api_post("/api/v2/delivery/recipient-access",{"recipient":recipient,"urls":batch})
            if response.get("contract_version")!="boi/recipient-access@1" or response.get("recipient")!=recipient:
                continue
            if identity is not None and response.get("recipient_identity")!=identity:
                results={};identity=None;break
            identity=response.get("recipient_identity")
            if not identity:continue
            results.update({u:response.get("access",{}).get(u,{}) for u in batch})
        except Exception:
            # An unavailable contract or failed check is visible uncertainty.
            continue
    def checked(url):
        status=results.get(url,{}).get("status")
        return True if status=="allowed" else False if status=="denied" else None
    if published:
        out=with_published_citations(value,recipient_check=checked)
    else:
        for answer in answers:
            links=list(dict.fromkeys(rendered_links(answer.get("readable_text",""))))
            old=access_notice(recipient_access(links))
            text=answer.get("readable_text","")
            if old and text.endswith(old):text=text[:-len(old)]
            access=recipient_access(links,check=checked)
            answer["recipient_citation_access"]=access
            answer["readable_text"]=text+access_notice(access)
        nav=out.get("delivery_navigation")
        if nav:
            answer=answers[nav["answer_index"]]
            nav["suffix"]=answer["readable_text"][nav["body_length"]:]
            nav["recipient_citation_access"]=answer["recipient_citation_access"]
    out["delivery_recipient"]={"selector":recipient,"identity":identity,
        "scope":"development default browser without credentials; not another signed-in session"}
    return out
