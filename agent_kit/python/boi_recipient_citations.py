"""Delivery-only recipient status; never an authorization grant.

check is an in-process, server/host-owned callback bound to an authenticated
recipient. It must check the exact target under that recipient's current rights.
Never construct it from caller/model flags or a caller-supplied employee ID.
No check means recipient unknown, even for public or caller-readable material.
"""
LABELS = {"allowed": "수신자 열람 가능", "denied": "수신자 열람 불가",
          "unknown": "수신자 열람 미확인"}


def recipient_access(urls, *, check=None):
    result = {}
    for url in dict.fromkeys(urls):
        status = "unknown"
        if check is not None:
            try:
                decision = check(url)
                status = "allowed" if decision is True else "denied" if decision is False else "unknown"
            except Exception:
                # Check failure is neither denial nor evidence of access.
                status = "unknown"
        result[url] = {"status": status, "label": LABELS[status],
                       "basis": "recipient_check" if status != "unknown" else "recipient_not_verified",
                       "grants_access": False}
    return result


def access_notice(access):
    statuses = {item["status"] for item in access.values()}
    notes = []
    if "denied" in statuses:
        notes.append("수신자 열람 불가인 인용이 있습니다. 해당 원문은 현재 수신자 권한으로 열 수 없습니다.")
    if "unknown" in statuses:
        notes.append("수신자 열람 미확인: 인용 링크가 받는 분의 권한으로 열리는지는 확인되지 않았습니다.")
    return "\n\n" + " ".join(notes) if notes else ""
