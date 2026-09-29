"""Final input-only audit before the first repair-model request."""
import ast
import json
import re
from collections import Counter
from pathlib import Path

from evaluation.interview_benchmark import save, verify_manifest
from scripts.expansion200_prepare import normalized
from scripts.holdout100_prepare import DATA, OUT, history, verify_agent


def audit():
    verify_agent()
    cases=verify_manifest(DATA/'manifest.json')['cases']
    assert len(cases)==100 and len({c['id'] for c in cases})==100
    assert Counter(c['provenance']['kind'] for c in cases)=={'mbpp_synthetic_mutation':80,'authored_documented_contract':20}
    known,names,prompts=history();seen=set();accepted_names=set();contracts=[]
    total_visible=0;total_hidden=0
    for case in cases:
        pre=json.loads((DATA/'preflight'/f"{case['id']}.json").read_text())
        assert pre['valid'] and pre['input_hashes']==case['hashes']
        source=Path(case['code_file']).read_text(encoding='utf-8')
        reference=Path(case['reference_file']).read_text(encoding='utf-8')
        for text in [source,reference]:
            key=normalized(text)
            assert key not in known and key not in seen, ('duplicate',case['id'])
            seen.add(key)
        assertions=[]
        for key in ['test_file','hidden_test_file']:
            tree=ast.parse(Path(case[key]).read_text(encoding='utf-8'))
            assertions.append({ast.dump(n,include_attributes=False) for n in ast.walk(tree) if isinstance(n,ast.Assert)})
        assert assertions[0] and assertions[1] and not assertions[0]&assertions[1], ('test_overlap',case['id'])
        total_visible+=len(assertions[0]);total_hidden+=len(assertions[1])
        if case['provenance']['kind']=='mbpp_synthetic_mutation':
            functions={n.name for n in ast.parse(reference).body if isinstance(n,ast.FunctionDef)}
            assert not functions&names and not functions&accepted_names
            accepted_names.update(functions)
            # Match the preparation prompt, without its appended signature instruction.
            text=case['requirement'].removesuffix(' Preserve the existing function signatures.')
            words=set(re.findall('[a-z]+',text.lower()))
            assert all(len(words&p)/len(words|p)<0.65 for p in prompts+contracts if words|p)
            contracts.append(words)
    result={'status':'PASS','tasks':100,'visible_assertions':total_visible,'heldout_assertions':total_hidden,
            'categories':dict(Counter(c['category'] for c in cases)),
            'agent_unchanged':True,'references_pass_both':True,'defects_fail_both':True,
            'no_assertion_overlap':True,'no_historical_or_within_set_normalized_duplicates':True,
            'semantic_independence_proven':False,'pretraining_contamination_excluded':False}
    save(OUT/'input_audit.json',result)
    return result


if __name__=='__main__':print(audit())
