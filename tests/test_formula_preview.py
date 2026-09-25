"""Synthetic helper closure for focused MCP release validation."""
import importlib.util


from tests.test_svid_parameter_catalog import row,request


def compile_it(formula,**kwargs):
    name='boi_api.app.governed_runtime.formula_preview'
    assert importlib.util.find_spec(name), 'Typed Formula compiler is not implemented'
    from boi_api.app.governed_runtime.formula_preview import compile_formula
    return compile_formula(formula,**kwargs)


def rev(ch):return {'ref':'KnowledgeRevision:sha256:'+ch*64,'revision_digest':'sha256:'+ch*64}


def units():return [
    {'unit_id':'pascal','dimension':'pressure','scale':'1','offset':'0','revision':rev('c')},
    {'unit_id':'kPa','dimension':'pressure','scale':'1000','offset':'0','revision':rev('d')},
    {'unit_id':'second','dimension':'time','scale':'1','offset':'0','revision':rev('e')},
    {'unit_id':'one','dimension':'dimensionless','scale':'1','offset':'0','revision':rev('f')}]


def lit(value,unit='pascal'):return {'kind':'quantity','value':str(value),'unit':unit}


def param():return {'kind':'parameter','binding':'p'}


def cmp(op='le',left=None,right=None):return {'kind':'compare','operator':op,'left':left or param(),'right':right or lit(1,'kPa')}


def formula(expression=None):return {'contract_version':'boi/formula-preview@1','parameters':{'p':request()},'expression':expression or cmp()}


def run(f=None,**kw):return compile_it(f or formula(),catalog=[row()],unit_definitions=units(),**kw)
