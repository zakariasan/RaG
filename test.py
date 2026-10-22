import json
from src.models import StudentSearchResultsAndAnswer
p = 'data/output/search_results/UnansweredQuestions/dataset_docs_public.json'
d = json.load(open(p));

json.dump(d, open('./mini_docs.json', 'w'))

with open('./.mini_docs.json')as f:
    fi = json.load(f)
print(f)

r = StudentSearchResultsAndAnswer.model_validate_json(fi)

print(len(r.search_results), all(x.answer for x in r.search_results))
