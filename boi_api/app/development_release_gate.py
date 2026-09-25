"""Shared read-only development acceptance decision; grants no authority."""
import json

def check_release(manifest, observations):
    issues=[]
    scopes=manifest.get('scopes',[])
    if not scopes or any(not s.get('members') for s in scopes):
        return [{'reason':'EMPTY_RELEASE_SCOPE'}]
    indexed={}
    for item in observations:
        key=json.dumps(item.get('revision'),sort_keys=True)
        if key in indexed:
            issues.append({'reason':'DUPLICATE_OBSERVATION','revision':item.get('revision')})
        indexed[key]=item
    seen=set()
    for scope in scopes:
        for expected in scope['members']:
            revision=expected['revision'];purpose=expected['purpose']
            key=json.dumps(revision,sort_keys=True); identity=(key,purpose)
            context={'scope':scope['name'],'revision':revision,'purpose':purpose}
            if identity in seen:
                issues.append({**context,'reason':'DUPLICATE_REQUIREMENT'})
                continue
            seen.add(identity)
            observed=indexed.get(key)
            if observed is None or observed.get('is_current_revision') is not True:
                issues.append({**context,'reason':'MISSING_OR_SUPERSEDED_REVISION'})
                continue
            uses=[u for u in observed.get('uses',[]) if u.get('purpose')==purpose]
            if len(uses)!=1:
                issues.append({**context,'reason':'MISSING_OR_AMBIGUOUS_USE'})
                continue
            use=uses[0]
            if (use.get('checker_current') is not True or use.get('policy_current') is not True
                or use.get('status') not in ('usable','usable_with_limits')):
                issues.append({**context,'reason':'REQUALIFICATION_REQUIRED'})
            if (use.get('status')!=expected['status'] or
                    use.get('limitations')!=expected['limitations']):
                issues.append({**context,'reason':'STATUS_OR_LIMITATIONS_CHANGED'})
    return issues
