"""Composition of existing authorized filters; no SQL or domain inference."""
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,model_validator


class FilterExpression(BaseModel):
    model_config=ConfigDict(extra='forbid',frozen=True)
    operator:Literal['filter','and','or','not']
    filter_index:int|None=Field(default=None,ge=0,strict=True)
    arguments:tuple['FilterExpression',...]=()

    @model_validator(mode='after')
    def shape(self):
        if self.operator=='filter':
            valid=self.filter_index is not None and not self.arguments
        else:
            valid=self.filter_index is None and (len(self.arguments)==1 if self.operator=='not' else len(self.arguments)>=2)
        if not valid:raise ValueError('FILTER_EXPRESSION_SHAPE_INVALID')
        return self


def validate_filter_expression(expression,filter_count):
    indices=set();nodes=0
    def visit(node,depth):
        nonlocal nodes
        nodes+=1
        if nodes>256 or depth>16:raise ValueError('FILTER_EXPRESSION_BUDGET_EXCEEDED')
        if node.operator=='filter':indices.add(node.filter_index)
        else:
            for child in node.arguments:visit(child,depth+1)
    visit(expression,1)
    if indices!=set(range(filter_count)):raise ValueError('FILTER_EXPRESSION_COVERAGE_MISMATCH')


def compose_filter_sql(expression,compiled_filters):
    """Only called with predicates already compiled from authorized mappings."""
    validate_filter_expression(expression,len(compiled_filters))
    def visit(node):
        if node.operator=='filter':return '('+compiled_filters[node.filter_index]+')'
        if node.operator=='not':return '(NOT '+visit(node.arguments[0])+')'
        return '('+(' AND ' if node.operator=='and' else ' OR ').join(visit(v) for v in node.arguments)+')'
    return visit(expression)


def conjoin_appended_filters(expression, original_count, appended_count):
    """Keep the request group intact under additional mandatory predicates."""
    if expression is None:
        return None  # Existing implicit conjunction already includes every filter.
    validate_filter_expression(expression, original_count)
    if not appended_count:
        return expression
    combined = FilterExpression(operator='and', arguments=(expression, *(
        FilterExpression(operator='filter', filter_index=index)
        for index in range(original_count, original_count + appended_count)
    )))
    validate_filter_expression(combined, original_count + appended_count)
    return combined
