"""Current, scoped direct-reference review bound to a browser confirmation.

Review records are immutable observations, not publication or semantic approval.
Local file bodies remain local. Count and page queries use the prepared DB index.
"""
from .domain_asset_staging import merge_writes
from .knowledge_space_store import EPOCHS
from .local_bundle_service import BUNDLES
from .local_impact_continuation import continuation
from .native_reference_guard import reference_guard_fences
from .semantic_binding_contract import RevisionRef, semantic_digest
from ..v2.atomic_store_contract import AtomicWrite

REVIEWS = 'knowledge_local_bundle_impacts'
VERSION = 'boi/local-bundle-reference-review@1'


class LocalBundleImpact:
    def __init__(self, bundles, sets, index):
        if bundles.store is not sets.store or index.backend is not sets.backend:
            raise ValueError('LOCAL_BUNDLE_IMPACT_BACKEND_MISMATCH')
        self.bundles,self.sets,self.index,self.store=bundles,sets,index,bundles.store

    def _contexts(self, actor_id, purpose='read'):
        actor=self.sets.spaces._actor(actor_id)
        # Audience is server-derived. A caller cannot omit another visible team
        # from the observation it asks the user to confirm.
        scopes=[{'visibility':'private'}, {'visibility':'public'},
            *({'visibility':'team','team_id':team} for team in sorted(set(actor.teams)))]
        if len(scopes)>256:
            raise ValueError('LOCAL_BUNDLE_IMPACT_SCOPE_LIMIT')
        return [self.sets._context(actor_id,scope,purpose) for scope in scopes]

    def _targets(self, auth, row, purpose='read'):
        refs=[*row['manifest']['existing_revisions'],
            *(c['current_revision'] for c in row['preview']['changes'] if c['current_revision'])]
        targets=tuple(sorted({RevisionRef.model_validate(r) for r in refs},key=lambda r:(r.ref,r.revision_digest)))
        # The immutable manifest bounds this to 500 existing and 500 changed
        # revisions. No whole population of IDs is materialized for a query.
        for target in targets:
            self.bundles.assets._record_metadata(auth,target,model_input=purpose == 'model_input',metadata_only=True)
        return targets

    @staticmethod
    def _binding(row):
        return {k:row[k] for k in ('bundle_ref','employee_id','manifest_digest','preview_digest')}

    def _validate(self, auth, row, review):
        if self._binding(row)!=review['binding']:
            raise ValueError('LOCAL_BUNDLE_IMPACT_BINDING_CHANGED')
        guards=reference_guard_fences(self.index,review['contexts'])
        expected,events,proof_fences=continuation(self.store,row,review['contexts'])
        purpose=review.get('purpose','read')
        if purpose not in ('read','model_input'):
            raise ValueError('LOCAL_BUNDLE_IMPACT_PURPOSE_INVALID')
        contexts=self._contexts(auth.principal,purpose)
        if [binding for binding,_ in contexts]!=expected:
            raise ValueError('LOCAL_BUNDLE_IMPACT_SCOPE_CHANGED')
        if [r.model_dump(mode='json') for r in self._targets(auth,row,purpose)]!=review['targets']:
            raise ValueError('LOCAL_BUNDLE_IMPACT_TARGETS_CHANGED')
        options={'own_events':events} if events else {}
        if any(self.index.changed(review['snapshot'],binding,**options) for binding,_ in contexts):
            raise ValueError('LOCAL_BUNDLE_IMPACT_SNAPSHOT_CHANGED')
        if [binding for binding,_ in self._contexts(auth.principal,purpose)]!=expected:
            raise ValueError('LOCAL_BUNDLE_IMPACT_SCOPE_CHANGED')
        if reference_guard_fences(self.index,expected)!=guards:
            raise ValueError('LOCAL_BUNDLE_IMPACT_SNAPSHOT_CHANGED')
        return contexts, (*guards,*proof_fences)

    @staticmethod
    def _view(review):
        return {'contract_version':VERSION,'impact_ref':review['impact_ref'],**review['binding'],
            'purpose':review.get('purpose','read'),
            'scopes':review['scopes'],'target_revision_count':len(review['targets']),
            'population_kind':'published_native_space_members',
            'coverage':'declared_native_dependencies_conflicts_supersedes_only',
            'scope_counts_overlap':True,'semantic_conflicts':'not_evaluated',
            'undeclared_related_candidates':'not_evaluated','transitive_impact':'not_evaluated',
            'legacy_outside_spaces':'not_evaluated','outside_accessible_scopes':'not_evaluated',
            'source_access_granted':False,'use_qualification_granted':False,
            'publication_authorized':False,'local_bytes_received':False}

    def prepare(self, *, authorization, bundle_ref, preview_digest, purpose='read'):
        if purpose not in ('read','model_input'):
            raise ValueError('LOCAL_BUNDLE_IMPACT_PURPOSE_INVALID')
        row=self.bundles._read(authorization,bundle_ref)
        if row['preview_digest']!=preview_digest:
            raise ValueError('LOCAL_BUNDLE_IMPACT_BINDING_CHANGED')
        if row['state']!='awaiting_confirmation':
            raise ValueError('LOCAL_BUNDLE_CONFIRMATION_NOT_PENDING')
        base_fences=self.bundles._current_basis(authorization,row)
        if purpose == 'model_input':
            base_fences=(*base_fences,*self.bundles._hotl_authority(authorization,row).fences)
        contexts=self._contexts(authorization.principal,purpose)
        targets=self._targets(authorization,row,purpose)
        snapshot=self.index.changes.snapshot()
        scopes=[{'target':binding['target'],**self.index.summary(binding,targets)} for binding,_ in contexts]
        material={'contract_version':VERSION,'binding':self._binding(row),
            'contexts':[binding for binding,_ in contexts],
            'targets':[t.model_dump(mode='json') for t in targets],'snapshot':snapshot,'scopes':scopes}
        if purpose == 'model_input':
            material['purpose']=purpose
        key='local-bundle-impact:'+semantic_digest(material)
        review={**material,'impact_ref':key,'employee_id':authorization.principal}
        current,guard_fences=self._validate(authorization,row,review)
        old=self.store.get(REVIEWS,key)
        if old is not None and any(old.get(k)!=v for k,v in review.items()):
            raise ValueError('LOCAL_BUNDLE_IMPACT_RECORD_CHANGED')
        fences=[AtomicWrite(EPOCHS,b['partition'],epoch,epoch or {'employee_id':b['partition'],'epoch':0})
            for b,epoch in current]
        writes=merge_writes((AtomicWrite(REVIEWS,key,old,old or review),
            AtomicWrite(BUNDLES,bundle_ref,row,row)),(*base_fences,*fences,*guard_fences))
        if not self.store.atomic_compare_and_write(writes):
            raise ValueError('LOCAL_BUNDLE_IMPACT_STATE_CHANGED')
        self._validate(authorization,self.bundles._read(authorization,bundle_ref),review)
        if purpose == 'model_input':
            self.bundles._hotl_authority(authorization,row)
        return self._view(review)

    def _read(self, auth, row, impact_ref):
        if not isinstance(impact_ref,str) or not impact_ref.startswith('local-bundle-impact:sha256:'):
            raise ValueError('LOCAL_BUNDLE_IMPACT_REVIEW_REQUIRED')
        review=self.store.get(REVIEWS,impact_ref)
        if not review or review.get('employee_id')!=auth.principal:
            raise ValueError('LOCAL_BUNDLE_IMPACT_ACCESS_DENIED')
        material={k:review[k] for k in ('contract_version','binding','contexts','targets','snapshot','scopes')}
        if 'purpose' in review:
            material['purpose']=review['purpose']
        if review.get('impact_ref')!=impact_ref or 'local-bundle-impact:'+semantic_digest(material)!=impact_ref:
            raise ValueError('LOCAL_BUNDLE_IMPACT_RECORD_CHANGED')
        if self._binding(row)!=review['binding']:
            raise ValueError('LOCAL_BUNDLE_IMPACT_BINDING_CHANGED')
        return review

    def confirmation_fences(self, *, authorization, row, impact_ref):
        review=self._read(authorization,row,impact_ref)
        contexts,guards=self._validate(authorization,row,review)
        return (*guards,AtomicWrite(REVIEWS,impact_ref,review,review),
            *(AtomicWrite(EPOCHS,b['partition'],epoch,epoch or {'employee_id':b['partition'],'epoch':0})
                for b,epoch in contexts))

    def page(self, *, authorization, bundle_ref, impact_ref, scope_index, cursor=None):
        row=self.bundles._read(authorization,bundle_ref)
        review=self._read(authorization,row,impact_ref)
        self._validate(authorization,row,review)
        if type(scope_index) is not int or not 0<=scope_index<len(review['contexts']):
            raise ValueError('LOCAL_BUNDLE_IMPACT_SCOPE_INVALID')
        after=''
        if cursor:
            saved=self.store.get(REVIEWS,cursor)
            if not saved or saved.get('employee_id')!=authorization.principal:
                raise ValueError('LOCAL_BUNDLE_IMPACT_CURSOR_DENIED')
            material={k:saved[k] for k in ('impact_ref','scope_index','after_id','employee_id')}
            if ('local-impact-cursor:'+semantic_digest(material)!=cursor or material['impact_ref']!=impact_ref
                    or material['scope_index']!=scope_index):
                raise ValueError('LOCAL_BUNDLE_IMPACT_CURSOR_CHANGED')
            after=material['after_id']
        result=self.index.page(review['contexts'][scope_index],
            tuple(RevisionRef.model_validate(t) for t in review['targets']),after,20)
        self._validate(authorization,self.bundles._read(authorization,bundle_ref),review)
        next_cursor=None
        if result['next_after_id']:
            material={'impact_ref':impact_ref,'scope_index':scope_index,'after_id':result['next_after_id'],
                'employee_id':authorization.principal}
            next_cursor='local-impact-cursor:'+semantic_digest(material)
            old=self.store.get(REVIEWS,next_cursor)
            if old is not None and any(old.get(k)!=v for k,v in material.items()):
                raise ValueError('LOCAL_BUNDLE_IMPACT_CURSOR_CHANGED')
            if not self.store.atomic_compare_and_write((AtomicWrite(REVIEWS,next_cursor,old,old or material),)):
                raise ValueError('LOCAL_BUNDLE_IMPACT_CURSOR_CHANGED')
            self._validate(authorization,self.bundles._read(authorization,bundle_ref),review)
        return {'impact_ref':impact_ref,'scope_index':scope_index,'items':result['items'],'next_cursor':next_cursor,
            'matching_visible_members':result['matching_visible_members'],'publication_authorized':False}
