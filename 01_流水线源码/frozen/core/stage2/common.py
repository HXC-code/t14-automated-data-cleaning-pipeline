"""Stage-2 paths and I/O. No external test or probability reader."""
import csv,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
STAGE=Path(__file__).resolve().parent
ROOT=STAGE.parent
sys.path.insert(0,str(ROOT))
from protocol import R,A,FEATURES,CAT,BOUNDS,CFG,Cleaner,corrupt,scores,arrays,fit_classifier
from candidates import CandidateBank,RepairEngine
OUT=STAGE/'output'
RECORDS=STAGE/'records'
CONFIG=json.loads((STAGE/'config.json').read_text(encoding='utf-8'))


def parts(seed):
    """Parse labels only for the pre-existing development IDs, never other rows."""
    import mmap
    ids=json.loads((ROOT/f'data/development_split_{seed}.json').read_text())['raw_ids']
    wanted={i for values in ids.values() for i in values};selected={}
    with open(Path(R.DATA)/'adult.data','rb') as handle:
        with mmap.mmap(handle.fileno(),0,access=mmap.ACCESS_READ) as data:
            start=0;i=0
            while start<len(data):
                end=data.find(b'\n',start)
                if end<0:end=len(data)
                if end>start:
                    if i in wanted:
                        values=[x.strip().rstrip('.') for x in data[start:end].decode('utf-8').split(',')]
                        assert len(values)==15
                        selected[i]={c:None if v in ['?',''] else float(v) if c in R.NUM else v for c,v in zip(R.COLS,values)}
                    i+=1
                start=end+1
    assert wanted==set(selected)
    return {k:[selected[i] for i in values] for k,values in ids.items()}


def write_csv(name,rows):
    if not rows:return
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def read_csv(name):
    with (OUT/name).open(encoding='utf-8-sig') as f:return list(csv.DictReader(f))


def save_json(name,obj):
    (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=lambda x:x.item()),encoding='utf-8')
