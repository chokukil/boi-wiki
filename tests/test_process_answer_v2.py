"""Synthetic helper closure for focused MCP release validation."""
from tests.test_process_answers import material


from tests.test_process_knowledge import sample


def inputs(sample):
    context,old,questions=material(sample)
    citation={'kind':'meaning',**old['answers'][0]['sentences'][0]['citations'][0]}
    draft={'context_digest':context['context_digest'],'answers':[{'question_id':'q','sentences':[
        {'text':'Coating applies film.','kind':'source_reported_fact','citations':[citation]}]}]}
    return draft,dict(context=context,sources=[sample['evidence']],questions=questions)
