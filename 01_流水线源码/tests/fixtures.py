"""Public unit fixtures use real training features and synthetic target tokens."""
import json
from copy import deepcopy
from src.paths import FINAL,feature_rows
from src.runtime import frozen_common,R,CORE


def install():
    _,features=feature_rows(FINAL/'test_fixtures/adult_features.csv')
    raw=[dict(r,income='>50K' if i%4==0 else '<=50K') for i,r in enumerate(features)]
    def parts(seed):
        ids=json.loads((CORE/f'data/development_split_{seed}.json').read_text())['raw_ids']
        return {k:[deepcopy(raw[i]) for i in values] for k,values in ids.items()}
    frozen_common.parts=parts;R.load_adult=lambda:deepcopy(raw)
    import protocol
    protocol.parts=parts
    return parts
