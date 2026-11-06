from pathlib import Path
import csv,hashlib,json,datetime
FINAL=Path(__file__).resolve().parents[1]
WORK=FINAL.parent
PRIVATE=WORK/'V3_3_J_FINAL_PRIVATE'
CONFIG=json.loads((FINAL/'config/final_protocol.json').read_text(encoding='utf-8'))
FEATURES=['age','workclass','fnlwgt','education','education_num','marital_status','occupation','relationship','race','sex','capital_gain','capital_loss','hours_per_week','native_country']
NUM=['age','fnlwgt','education_num','capital_gain','capital_loss','hours_per_week']


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_json(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path,obj):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    Path(path).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=lambda x:x.item()),encoding='utf-8')


def csvsave(path,rows):
    if not rows:return
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    with Path(path).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()


def feature_hash(row):
    return hashlib.sha256(json.dumps([row[c] for c in FEATURES],ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def feature_rows(path,uci=False):
    rows=[];ids=[]
    if uci:
        with Path(path).open('rb') as f:
            for line in f:
                if not line.strip():continue
                tokens=line.rsplit(b',',1)[0].decode('utf-8').split(',')
                if len(tokens)!=14:continue
                values=[v.strip().rstrip('.') for v in tokens]
                rows.append({c:None if v in ['?',''] else float(v) if c in NUM else v for c,v in zip(FEATURES,values)});ids.append(len(ids))
    else:
        with Path(path).open(encoding='utf-8-sig',newline='') as f:
            for r in csv.DictReader(f):
                rows.append({c:None if r[c] in ['?',''] else float(r[c]) if c in NUM else r[c] for c in FEATURES})
                ids.append(int(r['source_row_id']))
    return ids,rows
