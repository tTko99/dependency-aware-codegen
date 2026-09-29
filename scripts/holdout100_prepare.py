"""Deterministic holdout preparation; no model calls or outcome-based selection."""
import ast
import copy
import json
import re
import time
from pathlib import Path

from depguard.agent.runner import validate_candidate
from depguard.agent.safety import load_state, risk_findings
from depguard.execution import SandboxedExecutor
from depguard.schemas import to_jsonable
from evaluation.agent_benchmark import sha
from evaluation.interview_benchmark import now, save
from scripts.expansion200_prepare import normalized
from scripts.holdout100_authored import specs as authored

DATA = Path('data/holdout100_v1')
OUT = Path('results/holdout100_v1')
CHECKS = ['validate_packages','validate_apis','execute','run_pytest']


def verify_agent():
    frozen=json.loads((OUT/'agent_freeze.json').read_text())
    for p,h in frozen['sha256'].items():
        if sha(Path(p).read_bytes()) != h:
            raise ValueError('Frozen Agent/config changed: '+p)
    return frozen


def test_text(assertions, code, imports=()):
    functions={n.name for n in ast.parse(code).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
    class Names(ast.NodeTransformer):
        def visit_Name(self,node):
            if isinstance(node.ctx,ast.Load) and node.id in functions:
                return ast.copy_location(ast.Attribute(ast.Name('solution',ast.Load()),node.id,ast.Load()),node)
            return node
    body=['import solution',*imports,'']
    for i, assertion in enumerate(assertions):
        tree=Names().visit(ast.parse(assertion)); ast.fix_missing_locations(tree)
        body += [f'def test_contract_{i}():',*['    '+x for x in ast.unparse(tree).splitlines()],'']
    return '\n'.join(body)


def mutations(code, task):
    tree=ast.parse(code);result=[]
    swaps={ast.Add:ast.Sub,ast.Sub:ast.Add,ast.Mult:ast.Add,ast.FloorDiv:ast.Mod,
           ast.Mod:ast.FloorDiv,ast.Lt:ast.LtE,ast.LtE:ast.Lt,ast.Gt:ast.GtE,
           ast.GtE:ast.Gt,ast.Eq:ast.NotEq,ast.NotEq:ast.Eq,ast.And:ast.Or,ast.Or:ast.And}
    for i,node in enumerate(ast.walk(tree)):
        edits=[]
        if isinstance(node,(ast.BinOp,ast.BoolOp)) and type(node.op) in swaps:
            edits=[('op',swaps[type(node.op)](),'operator')]
        elif isinstance(node,ast.Compare) and node.ops and type(node.ops[0]) in swaps:
            edits=[('ops',[swaps[type(node.ops[0])]()]+node.ops[1:],'comparison')]
        elif isinstance(node,ast.Constant) and type(node.value) is int and -2<=node.value<=10:
            edits=[('value',node.value+1,'boundary_constant')]
        elif isinstance(node,ast.Attribute) and node.attr in {'append','extend','sort','reverse','split','strip','find','count','ceil','floor'}:
            edits=[('attr',node.attr+'_missing','api_name')]
        for field,value,kind in edits:
            changed=copy.deepcopy(tree);target=list(ast.walk(changed))[i];setattr(target,field,value)
            text=ast.unparse(changed)+'\n'
            result.append((sha(f'holdout100-v1:{task}:{i}:{kind}'.encode()),text,{'kind':kind,'node_index':i,'line':getattr(node,'lineno',None)}))
    return sorted(result)[:16]


def history():
    hashes={}; names=set();prompts=[]
    for p in Path('data').rglob('*.py'):
        if DATA in p.parents or p.name not in {'input.py','reference.py'}:
            continue
        try:
            text=p.read_text(encoding='utf-8-sig'); hashes[normalized(text)]=str(p)
            names.update(n.name for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name!='solve')
        except (SyntaxError,UnicodeError):
            continue
    for p in Path('data').rglob('requirement.txt'):
        if DATA not in p.parents:
            prompts.append(set(re.findall(r'[a-z]+',p.read_text(encoding='utf-8').lower())))
    return hashes,names,prompts


def run(code, tests):
    risks=risk_findings(code)+risk_findings(tests)
    if risks:return {'status':'denied','risks':risks}
    return to_jsonable(SandboxedExecutor(timeout_seconds=5).execute(code,tests))


def valid_failure(row):
    return row['status']=='failed' and row.get('return_code')==1 and ('FAILED' in row.get('stdout',''))


def materialize(spec, evidence):
    folder=DATA/'cases'/spec['id'];folder.mkdir(parents=True,exist_ok=True)
    texts={'input.py':spec['source'],'reference.py':spec['reference'],
           'test_visible.py':spec['tests'],'test_hidden.py':spec['hidden_tests'],
           'requirement.txt':spec['requirement']}
    for name,text in texts.items():(folder/name).write_text(text,encoding='utf-8',newline='\n')
    case={'id':spec['id'],'family':spec['provenance']['family'],'category':spec['category'],
          'cohort':'hard','is_control':False,'requirement':spec['requirement'],
          'code_file':(folder/'input.py').as_posix(),'test_file':(folder/'test_visible.py').as_posix(),
          'reference_file':(folder/'reference.py').as_posix(),'hidden_test_file':(folder/'test_hidden.py').as_posix(),
          'hashes':{n:sha(t.encode()) for n,t in texts.items()},'required_checks':CHECKS,
          'provenance':spec['provenance'],'control_parent':None}
    prior_path=DATA/'preflight'/f"{spec['id']}.json"
    if prior_path.exists():
        prior=json.loads(prior_path.read_text(encoding='utf-8'))
        if prior['valid'] and prior['input_hashes']==case['hashes']:
            return case
    audits={}
    for label,test in [('visible','test_file'),('hidden','hidden_test_file')]:
        state=load_state(case['reference_file'],case[test],project_root=folder,
                         execution_timeout_seconds=10,validation_config={'required_checks':CHECKS})
        audits[label]=validate_candidate(state,time.monotonic()+45)
    valid=all(r['host_status']=='PASS' for r in audits.values())
    save(DATA/'preflight'/f"{spec['id']}.json",{'valid':valid,'evidence':evidence,'reference_host':audits,'input_hashes':case['hashes']})
    return case if valid else None


def main():
    verify_agent()
    for spec in authored():
        for part in ['visible','hidden']:
            test_text(spec[part],spec['reference'])
    if (DATA/'manifest.json').exists():raise ValueError('Already frozen')
    DATA.mkdir(exist_ok=True)
    (DATA/'ruff.toml').write_text('exclude = ["cases", "upstream"]\n')
    known,names,prompts=history();selected=[];decisions=[]
    rows=json.loads((DATA/'upstream/mbpp/sanitized-mbpp.json').read_text())
    revision=json.loads((DATA/'upstream/mbpp/inventory.json').read_text())['revision']
    for row in sorted(rows,key=lambda r:sha(f"holdout100-v1:{r['task_id']}".encode())):
        if sum(c['provenance']['kind']=='mbpp_synthetic_mutation' for c in selected)==80:break
        name='mbpp_'+str(row['task_id']);code=row['code'];decision={'id':name,'selected':False}
        decisions.append(decision)
        assertions=list(dict.fromkeys(row['test_list']))
        functions={n.name for n in ast.parse(code).body if isinstance(n,ast.FunctionDef)}
        words=set(re.findall(r'[a-z]+',row['prompt'].lower()))
        near=max((len(words&p)/len(words|p) for p in prompts if words|p),default=0)
        if len(assertions)<3 or len(code)>6000 or len(code.splitlines())>120:
            decision['reason']='size_or_test_count';continue
        if normalized(code) in known or functions&names or near>=0.65:
            decision.update(reason='historical_duplicate_or_near_contract',similarity=near);continue
        assertions.sort(key=lambda t:sha(f"holdout100-tests:{row['task_id']}:{t}".encode()))
        split=max(1,len(assertions)//2)
        visible=test_text(assertions[:split],code,row['test_imports'])
        hidden=test_text(assertions[split:],code,row['test_imports'])
        rv=run(code,visible);rh=run(code,hidden)
        if rv['status']!='passed' or rh['status']!='passed':
            decision.update(reason='reference_preflight',visible=rv,hidden=rh);continue
        decision['mutants']=[]
        for _,bad,mutation in mutations(code,row['task_id']):
            if normalized(bad) in known:continue
            bv=run(bad,visible)
            if not valid_failure(bv):
                decision['mutants'].append({'mutation':mutation,'visible':bv,'reason':'not_visible_test_failure'});continue
            bh=run(bad,hidden)
            decision['mutants'].append({'mutation':mutation,'visible':bv,'hidden':bh})
            if not valid_failure(bh):continue
            category='api_usage' if mutation['kind']=='api_name' else ('boundary' if mutation['kind'] in {'comparison','boundary_constant'} else ('data_processing' if any(x in row['prompt'].lower() for x in ['list','string','tuple','dictionary']) else 'algorithm'))
            spec={'id':name,'source':bad,'reference':code,'tests':visible,'hidden_tests':hidden,
                  'requirement':row['prompt']+' Preserve the existing function signatures.', 'category':category,
                  'provenance':{'kind':'mbpp_synthetic_mutation','task_id':row['task_id'],'family':','.join(sorted(functions)),
                    'revision':revision,'url':f'https://github.com/google-research/google-research/blob/{revision}/mbpp/sanitized-mbpp.json',
                    'production_bug':False,'license':'Apache-2.0 repository license (archived)', 'mutation':mutation,
                    'test_split':'deduplicated upstream assertions, fixed hash split; heldout not shown'}}
            case=materialize(spec,{'bug_visible':bv,'bug_hidden':bh,'reference_visible':rv,'reference_hidden':rh})
            if case:
                selected.append(case);known[normalized(code)]=name;known[normalized(bad)]=name
                names.update(functions);prompts.append(words)
                decision['selected']=True;print('Selected',len(selected),name,flush=True)
                break
        save(DATA/'selection_progress.json',{'at':now(),'selected':len(selected),'decisions':decisions})
    if len(selected)!=80:raise ValueError(f'Only {len(selected)} public tasks eligible; no silent policy changes')
    for spec in authored():
        spec['tests']=test_text(spec['visible'],spec['reference']);spec['hidden_tests']=test_text(spec['hidden'],spec['reference'])
        if normalized(spec['reference']) in known or normalized(spec['source']) in known:
            raise ValueError('Authored duplicate: '+spec['id'])
        evidence={f'{label}_{part}':run(spec[key],spec[test]) for label,key in [('bug','source'),('reference','reference')]
                  for part,test in [('visible','tests'),('hidden','hidden_tests')]}
        if not all(evidence['reference_'+p]['status']=='passed' and valid_failure(evidence['bug_'+p]) for p in ['visible','hidden']):
            save(DATA/'authored_rejection.json',{'id':spec['id'],'evidence':evidence});raise ValueError('Authored preflight failed: '+spec['id'])
        case=materialize(spec,evidence)
        if not case:raise ValueError('Authored host rejected: '+spec['id'])
        selected.append(case);known[normalized(spec['reference'])]=spec['id'];known[normalized(spec['source'])]=spec['id']
        print('Selected',len(selected),spec['id'],flush=True)
    verify_agent()
    save(DATA/'manifest.json',{'name':'holdout100_v1','cases':selected,'configs':{'configs/m7_qwen3_30b.json':sha(Path('configs/m7_qwen3_30b.json').read_bytes())}})
    save(DATA/'selection.json',{'frozen_at':now(),'count':100,'decisions':decisions,'policy':'docs/HOLDOUT100_PLAN.md'})
    print('PREPARATION COMPLETE',flush=True)


if __name__=='__main__':main()
