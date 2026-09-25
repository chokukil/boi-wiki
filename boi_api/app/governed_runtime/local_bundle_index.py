"""Bounded metadata reads for a validated bundle, never an authority grant."""
from itertools import islice


def read_bundle_index(store, collection, keys):
    # 1,100 objects + 500 proposal preflights + one completed-preflight row.
    keys=tuple(islice(iter(keys),1602))
    if len(keys)>1601:
        raise ValueError('LOCAL_BUNDLE_INDEX_READ_LIMIT')
    result={}
    for start in range(0,len(keys),1000):
        result.update(store.get_many(collection,list(keys[start:start+1000])))
    return result
