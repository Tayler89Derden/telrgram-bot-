#!/usr/bin/env python3
from __future__ import annotations
import csv,gzip,hashlib,io,json,urllib.request,urllib.error,zipfile
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import date,timedelta
from pathlib import Path

SYMBOLS=['BTCUSDT','SOLUSDT','XRPUSDT']
START=date(2023,12,1); END=date(2025,12,31)
BASE='https://data.binance.vision/data/futures/um/daily/metrics/{s}/{s}-metrics-{d}.zip'
OUT=Path('artifacts/binance_metrics_2024_2025'); OUT.mkdir(parents=True,exist_ok=True)

def days(a,b):
 d=a
 while d<=b:
  yield d; d+=timedelta(days=1)

def fetch(sym,d):
 ds=d.isoformat(); u=BASE.format(s=sym,d=ds)
 try:
  req=urllib.request.Request(u,headers={'User-Agent':'AIRM-research/1.0'})
  with urllib.request.urlopen(req,timeout=30) as r: raw=r.read()
  with zipfile.ZipFile(io.BytesIO(raw)) as z:
   names=[n for n in z.namelist() if not n.endswith('/')]
   if not names:return sym,ds,None,'EMPTY_ZIP'
   body=z.read(names[0]).decode('utf-8-sig',errors='replace')
  return sym,ds,body,None
 except urllib.error.HTTPError as e:return sym,ds,None,f'HTTP_{e.code}'
 except Exception as e:return sym,ds,None,f'{type(e).__name__}:{e}'

def main():
 ds=list(days(START,END)); tasks=[(s,d) for s in SYMBOLS for d in ds]
 by={s:{} for s in SYMBOLS}; errors=[]
 print('ARCHIVE_START',len(tasks),flush=True)
 with ThreadPoolExecutor(max_workers=32) as ex:
  futs=[ex.submit(fetch,s,d) for s,d in tasks]
  for i,f in enumerate(as_completed(futs),1):
   s,d,body,err=f.result()
   if body is not None:by[s][d]=body
   else:errors.append({'symbol':s,'date':d,'error':err})
   if i%100==0:print('PROGRESS',i,'ok',sum(map(len,by.values())),'err',len(errors),flush=True)
 manifest={'source':'Binance Data Vision USD-M daily metrics','start':START.isoformat(),'end':END.isoformat(),'symbols':{},'errors':errors}
 for s in SYMBOLS:
  p=OUT/f'{s}_metrics_{START}_{END}.csv.gz'; header=None; rows=0; covered=[]
  with gzip.open(p,'wt',encoding='utf-8',newline='') as g:
   w=None
   for d in sorted(by[s]):
    rd=csv.reader(io.StringIO(by[s][d]))
    try:h=[x.strip() for x in next(rd)]
    except StopIteration:continue
    if header is None:header=h;w=csv.writer(g);w.writerow(h)
    elif h!=header:
     errors.append({'symbol':s,'date':d,'error':'HEADER_MISMATCH'});continue
    n=0
    for row in rd:
     if row:w.writerow(row);n+=1
    if n:rows+=n;covered.append(d)
  sha=hashlib.sha256(p.read_bytes()).hexdigest()
  manifest['symbols'][s]={'file':p.name,'sha256':sha,'bytes':p.stat().st_size,'rows':rows,'days_ok':len(covered),'days_requested':len(ds),'first_day':covered[0] if covered else None,'last_day':covered[-1] if covered else None,'header':header}
  print('ARCHIVE_SYMBOL',s,json.dumps(manifest['symbols'][s],sort_keys=True),flush=True)
 (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
 print('ARCHIVE_DONE errors',len(errors),flush=True)
 for s,v in manifest['symbols'].items():
  if v['days_ok']<int(v['days_requested']*.98):raise SystemExit(f'COVERAGE_FAIL:{s}:{v["days_ok"]}/{v["days_requested"]}')
if __name__=='__main__':main()
