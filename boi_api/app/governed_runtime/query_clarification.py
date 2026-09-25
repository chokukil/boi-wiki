"""One-turn clarification continuation in the shared immutable Run ledger.

No query compilation, execution, semantic rewrite, approval or Release authority.
Channel is deliberately absent from identity and authorization bindings.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json

from .ledger import GovernedRuntimeLedger, RecordKind, sha256_id


def _digest(value):
    return 'sha256:' + hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,
                                               separators=(',',':')).encode()).hexdigest()


def _time(value):
    parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
    if parsed.tzinfo is None: raise ValueError('CLARIFICATION_TIME_OFFSET_REQUIRED')
    return parsed


class QueryClarificationStore:
    SCHEMA='boi-query-clarification/v1'

    def __init__(self,ledger: GovernedRuntimeLedger):
        self.ledger=ledger

    def _read(self,ref):
        record=self.ledger.read(ref)
        envelope={'schema':self.ledger.SCHEMA,'kind':record.kind.value,'authority':record.authority,
                  'occurred_at':record.occurred_at,'payload':record.payload}
        if (record.kind!=RecordKind.RUN or record.authority!='executor'
                or sha256_id(record.kind,envelope)!=ref):
            raise ValueError('CLARIFICATION_RECORD_INTEGRITY_INVALID')
        return record

    def _find(self,kind,key):
        for path in (self.ledger.records_root/'Run').glob('*.json'):
            value=json.loads(path.read_text())
            payload=value.get('payload',{})
            if payload.get('schema')==self.SCHEMA and payload.get('kind')==kind and payload.get('key')==key:
                return self._read(value['record_id'])
        return None

    def _append(self,kind,key,payload,occurred_at):
        return self.ledger._append_locked(RecordKind.RUN,
            {'schema':self.SCHEMA,'kind':kind,'key':key,**payload},
            authority='executor',occurred_at=occurred_at)

    @staticmethod
    def _public(record):
        return {'ref':record.record_id,'options':record.payload['options'],
                'expires_at':record.payload['expires_at'],'remaining_clarifications':1}

    def issue(self,*,request_id,binding,alternatives,candidate_digest,occurred_at):
        if not 2<=len(alternatives)<=4: raise ValueError('CLARIFICATION_ALTERNATIVES_INVALID')
        options=[]
        for item in alternatives:
            if not item.get('label') or not item.get('logical_ids'):
                raise ValueError('CLARIFICATION_ALTERNATIVES_INVALID')
            options.append({**item,'option_id':_digest(item)})
        if len({o['option_id'] for o in options})!=len(options):
            raise ValueError('CLARIFICATION_ALTERNATIVES_INVALID')
        key=_digest({'request_id':request_id,'binding':binding})
        with self.ledger._locked():
            existing=self._find('challenge',key)
            if existing:
                if existing.payload['options']!=options or existing.payload['candidate_digest']!=candidate_digest:
                    raise ValueError('CLARIFICATION_REQUEST_CONFLICT')
                return self._public(existing)
            expires=(_time(occurred_at)+timedelta(minutes=15)).astimezone(timezone.utc).isoformat()
            record=self._append('challenge',key,{'binding':binding,'options':options,
                'candidate_digest':candidate_digest,'expires_at':expires},occurred_at)
            return self._public(record)

    def accept(self,*,challenge_ref,option_id,binding,occurred_at):
        with self.ledger._locked():
            challenge=self._read(challenge_ref)
            if challenge.payload.get('schema')!=self.SCHEMA or challenge.payload.get('kind')!='challenge':
                raise ValueError('CLARIFICATION_REF_INVALID')
            payload=challenge.payload
            if payload['binding']!=binding: raise ValueError('CLARIFICATION_BINDING_MISMATCH')
            if _time(occurred_at)>=_time(payload['expires_at']): raise ValueError('CLARIFICATION_EXPIRED')
            if _time(occurred_at)<_time(challenge.occurred_at): raise ValueError('CLARIFICATION_TIME_INVALID')
            selected=next((o for o in payload['options'] if o['option_id']==option_id),None)
            if selected is None: raise ValueError('CLARIFICATION_OPTION_INVALID')
            prior=self._find('reply',challenge_ref)
            if prior:
                if prior.payload['context']['selected_alternative']!=selected:
                    raise ValueError('CLARIFICATION_ALREADY_ANSWERED')
                return prior.payload['context']
            context={'schema':self.SCHEMA,'challenge_ref':challenge_ref,
                'original_question':binding['question'],'selected_alternative':selected,
                'alternatives':payload['options'],'context_digest':binding['context_digest'],
                'remaining_clarifications':0}
            context['reply_digest']=_digest(context)
            self._append('reply',challenge_ref,{'context':context},occurred_at)
            return context

    def reserve_inference(self,context,*,occurred_at):
        key=context['reply_digest']
        with self.ledger._locked():
            completed=self._find('inference_result',key)
            if completed: return completed.payload['result']
            if self._find('inference_reservation',key):
                raise ValueError('CLARIFICATION_INFERENCE_IN_PROGRESS')
            self._append('inference_reservation',key,{'challenge_ref':context['challenge_ref']},occurred_at)
        return None

    def finish_inference(self,context,result,*,occurred_at):
        key=context['reply_digest']
        with self.ledger._locked():
            prior=self._find('inference_result',key)
            if prior:
                if prior.payload['result']!=result: raise ValueError('CLARIFICATION_INFERENCE_CONFLICT')
                return
            if not self._find('inference_reservation',key):
                raise ValueError('CLARIFICATION_INFERENCE_NOT_RESERVED')
            self._append('inference_result',key,{'result':result},occurred_at)
