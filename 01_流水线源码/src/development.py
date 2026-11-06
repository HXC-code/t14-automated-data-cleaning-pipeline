"""Private development-label reader; no official test or sealed-label input."""
import json
from src.paths import FINAL,WORK,FEATURES,feature_rows


def load(seed):
    ids=json.loads((FINAL/f'frozen/core/data/development_split_{seed}.json').read_text())['raw_ids']
    _,features=feature_rows(FINAL/'test_fixtures/adult_features.csv')
    needed=set(ids['downstream_fit']+ids['classifier_validation']);labels={};i=0
    with (WORK/'V3.3/legacy/data/adult.data').open('rb') as f:
        for line in f:
            if not line.strip():continue
            if i in needed:
                token=line.rsplit(b',',1)[1].strip().rstrip(b'.')
                assert token in [b'>50K',b'<=50K'];labels[i]=int(token==b'>50K')
            i+=1
    assert set(labels)==needed
    return dict(reference=[features[i] for i in ids['reference']],fit=[features[i] for i in ids['downstream_fit']],validation=[features[i] for i in ids['classifier_validation']],
                y=[labels[i] for i in ids['downstream_fit']+ids['classifier_validation']],raw_ids=ids['downstream_fit']+ids['classifier_validation'],reference_ids=ids['reference'])
