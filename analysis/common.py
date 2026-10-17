"""Read saved records only; never import the GPU trainer or execute candidate code."""
from pathlib import Path
import csv,io,json,hashlib
ROOT=Path(__file__).resolve().parents[1]
def load(path): return json.loads((ROOT/path).read_text(encoding='utf-8-sig'))
def rows(path): return list(csv.DictReader(io.StringIO((ROOT/path).read_bytes().decode('utf-8-sig'))))
def sha(data): return hashlib.sha256(data).hexdigest()
def save(path,data):
 # Explicit bytes keep newly generated JSON canonical LF on every platform.
 p=ROOT/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((json.dumps(data,indent=2,ensure_ascii=False)+'\n').encode('utf-8'))
def matrix():return load('training/configs/formal_matrix.json')
def runpath(run):return f'data/formal/{run["condition"]}/run-{run["run"]}'
