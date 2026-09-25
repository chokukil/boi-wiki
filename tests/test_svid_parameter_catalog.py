"""Synthetic helper closure for focused MCP release validation."""
def row(model='M1',component='zone-a',revision='a'):
    return {'identity':{'namespace':'plant-x','model':model,'svid':'9'},
        'revision':{'ref':'KnowledgeRevision:sha256:'+revision*64,'revision_digest':'sha256:'+revision*64},
        'parameter_name':'P','quantity':'pressure','unit':'pascal','component':component,
        'binding_status':'unverified','source_locator':'source/zone-a'}


def request(**changes):
    r={'identity':{'namespace':'plant-x','model':'M1','svid':'9'},'revision':row()['revision'],
       'component':'zone-a','quantity':'pressure','unit':'pascal'}
    r.update(changes);return r
