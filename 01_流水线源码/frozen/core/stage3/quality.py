"""Offline evaluation only. No result of this module feeds candidate gates."""
from common import FEATURES


def quality(clean,dirty,result,truth,bank,field=None):
    cols=[field] if field else FEATURES;keys={k for k in truth if k[1] in cols}
    changed={(i,c) for i in range(len(dirty)) for c in cols if dirty[i][c]!=result['rows'][i][c]}
    exact=sum(result['rows'][i][c]==clean[i][c] for i,c in changed)
    cleanwrong=sum(result['rows'][i][c]!=clean[i][c] for i,c in changed-keys)
    strict=sum(result['rows'][i][c]==clean[i][c] for i,c in keys)
    reasonable=sum(result['rows'][i][c]!=clean[i][c] and bank.reliable(c,result['rows'][i][c]) for i,c in changed&keys)
    q=dict(injected=len(keys),detected=len(keys&result['flags']),auto_modified=len(changed),strict_modified=exact,strict_restored=strict,
           reasonable_only=reasonable,wrong_modified=len(changed)-exact,clean_misrepair=cleanwrong,clean_cells=len(clean)*len(cols)-len(keys),
           manual_review=len({(r['row'],r['col']) for r in result['review'] if r['col'] in cols}),
           withheld=sum(r['col'] in cols for r in result['withheld']),dependency_withheld=sum(r['col'] in cols and 'upstream_dependency_withdrawn' in r['reasons'] for r in result['withheld']),
           fractional_modifications=sum(c=='fnlwgt' and result['rows'][i][c] is not None and not float(result['rows'][i][c]).is_integer() for i,c in changed))
    q.update(auto_precision=exact/len(changed) if changed else None,restoration_rate=strict/len(keys) if keys else None,
             clean_misrepair_rate=cleanwrong/q['clean_cells'],semantic_cases=len(result['semantic_cases']))
    return q
