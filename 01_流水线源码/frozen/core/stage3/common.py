"""Stage-three paths and development-ID-only input reader."""
import csv,json,sys,hashlib,importlib.util
from pathlib import Path
sys.dont_write_bytecode=True
STAGE=Path(__file__).resolve().parent;ROOT=STAGE.parent
sys.path.insert(0,str(ROOT))
from protocol import R,A,FEATURES,CAT,BOUNDS,Cleaner,corrupt,scores,arrays
from candidates import CandidateBank,RepairEngine
CONFIG=json.loads((STAGE/'config.json').read_text(encoding='utf-8'))
OUT=STAGE/'output';RECORDS=STAGE/'records';INPUTS=STAGE/'inputs'


def parts(seed):
    spec=importlib.util.spec_from_file_location('stage2_development_reader',ROOT/'stage2/common.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module.parts(seed)


def write_csv(name,rows):
    if not rows:return
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def save(path,obj):
    Path(path).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=lambda x:x.item()),encoding='utf-8')


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def full_signature(rows):
    return hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')).hexdigest()
