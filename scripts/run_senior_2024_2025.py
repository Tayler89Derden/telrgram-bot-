#!/usr/bin/env python3
from __future__ import annotations
import io,json,zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
import numpy as np
import pandas as pd
import requests

START=pd.Timestamp('2024-01-01',tz='UTC'); END=pd.Timestamp('2026-01-01',tz='UTC')
KCOL=['open_time','open','high','low','close','volume','close_time','quote_volume','count','taker_buy_volume','taker_buy_quote_volume','ignore']
MCOL=['create_time','symbol','sum_open_interest','sum_open_interest_value','count_toptrader_long_short_ratio','sum_toptrader_long_short_ratio','count_long_short_ratio','sum_taker_long_short_vol_ratio']
ORIGINAL_SENIOR_RT=.0014
ST_CACHE={}
METRICS=Path('artifacts/binance_metrics_2024_2025')
OUT=Path('artifacts/senior_2024_2025');OUT.mkdir(parents=True,exist_ok=True)
SOURCE_BLOB_SHA='93257ca37c4402adec35ced28c846f0fc29e85cd'

def months(a,b):
 y,m=map(int,a.split('-'));y2,m2=map(int,b.split('-'))
 while (y,m)<=(y2,m2):
  yield f'{y:04d}-{m:02d}';m+=1
  if m==13:y+=1;m=1

def getzip(url,timeout=40):
 try:
  r=requests.get(url,timeout=timeout);r.raise_for_status()
  with zipfile.ZipFile(io.BytesIO(r.content)) as z:return z.read(z.namelist()[0])
 except Exception:return None

def parse_kline(raw):
 p=pd.read_csv(io.BytesIO(raw));norm=str(p.columns[0]).strip().lower().replace(' ','_') if len(p.columns) else ''
 if len(p.columns)!=12 or norm!='open_time':p=pd.read_csv(io.BytesIO(raw),header=None,names=KCOL)
 else:p.columns=KCOL
 for c in KCOL:p[c]=pd.to_numeric(p[c],errors='coerce')
 p=p.dropna(subset=['open_time','open','high','low','close']);ot=p.open_time.astype('int64').to_numpy();ot=np.where(ot>10**14,ot//1000,ot)
 p['time']=pd.to_datetime(ot,unit='ms',utc=True);return p.set_index('time')

def load_klines(sym,tf,a,b):
 urls=[f'https://data.binance.vision/data/futures/um/monthly/klines/{sym}/{tf}/{sym}-{tf}-{ym}.zip' for ym in months(a,b)];arr=[]
 with ThreadPoolExecutor(max_workers=16) as ex:
  for raw in ex.map(getzip,urls):
   if raw is not None:
    try:arr.append(parse_kline(raw))
    except Exception:pass
 if not arr:raise RuntimeError(f'NO_KLINES {sym} {tf}')
 d=pd.concat(arr).sort_index();return d[~d.index.duplicated(keep='last')]

def load_metrics_raw(sym):
 p=METRICS/f'{sym}_metrics_2023-12-01_2025-12-31.csv.gz'
 m=pd.read_csv(p,compression='gzip')
 if len(m.columns)!=8:m.columns=MCOL
 else:m.columns=MCOL
 m['time']=pd.to_datetime(m.create_time,utc=True,errors='coerce')
 for c in MCOL[2:]:m[c]=pd.to_numeric(m[c],errors='coerce')
 return m.dropna(subset=['time']).sort_values('time').drop_duplicates('time').set_index('time')

def atr(d,n=14):
 pc=d.close.shift();tr=np.maximum(d.high-d.low,np.maximum((d.high-pc).abs(),(d.low-pc).abs()));return tr.ewm(alpha=1/n,adjust=False,min_periods=n).mean()

def make4(h):
 q=h.resample('4h',label='left',closed='left').agg(open=('open','first'),high=('high','max'),low=('low','min'),close=('close','last'),quote_volume=('quote_volume','sum'),count=('count','sum'),taker_buy_quote_volume=('taker_buy_quote_volume','sum')).dropna();q['atr']=atr(q);return q

def enrich(h,q,mraw):
 x=h.copy();signed=2*x.taker_buy_quote_volume-x.quote_volume
 for n in [1,3,6,12,24]:
  x[f'ret{n}']=x.close/x.close.shift(n)-1;x[f'taker{n}']=signed.rolling(n,min_periods=max(1,n//3)).sum()/x.quote_volume.rolling(n,min_periods=max(1,n//3)).sum().replace(0,np.nan)
 lr=np.log(x.close/x.close.shift());ab=lr.abs();pp=(lr>0).astype(float).rolling(24,min_periods=8).mean();eps=1e-12
 x['ent24']=-(pp*np.log(pp+eps)+(1-pp)*np.log(1-pp+eps))/np.log(2)
 for n in [6,12]:x[f'eff{n}']=np.log(x.close/x.close.shift(n)).abs()/ab.rolling(n,min_periods=max(2,n//3)).sum().replace(0,np.nan)
 for c,base in [('quote_volume','vol'),('count','count')]:
  z=np.log1p(x[c]);mu=z.rolling(72,min_periods=24).mean().shift(1);sd=z.rolling(72,min_periods=24).std().shift(1);x[f'{base}_z72']=(z-mu)/sd.replace(0,np.nan)
 qr=q.copy();qr['h4_ret1']=qr.close/qr.close.shift(1)-1;qr['h4_ret6']=qr.close/qr.close.shift(6)-1;x=x.join(qr[['h4_ret1','h4_ret6']].shift(1).reindex(x.index,method='ffill'))
 if not mraw.empty:
  mm=mraw.resample('1h',label='left',closed='left').last();mm['oi_chg4']=mm.sum_open_interest_value/mm.sum_open_interest_value.shift(4)-1;mm['oi_chg12']=mm.sum_open_interest_value/mm.sum_open_interest_value.shift(12)-1;mm['oi_chg24']=mm.sum_open_interest_value/mm.sum_open_interest_value.shift(24)-1
  mm['metric_taker']=(mm.sum_taker_long_short_vol_ratio-1)/(mm.sum_taker_long_short_vol_ratio+1)
  for c in ['count_toptrader_long_short_ratio','sum_toptrader_long_short_ratio','count_long_short_ratio']:mm['log_'+c]=np.log(mm[c].replace(0,np.nan))
  keep=['oi_chg4','oi_chg12','oi_chg24','metric_taker','log_count_toptrader_long_short_ratio','log_sum_toptrader_long_short_ratio','log_count_long_short_ratio'];x=x.join(mm[keep].reindex(x.index))
 return x

def effective4(q,h1):
 rows=[];prev=None
 for t,r in q.iterrows():
  hi=float(r.high);lo=float(r.low)
  if prev is not None and hi<=prev['high'] and lo>=prev['low']:continue
  outside=prev is not None and hi>prev['high'] and lo<prev['low'];z=h1.loc[(h1.index>=t)&(h1.index<t+pd.Timedelta(hours=4))];ht=z.high.idxmax() if len(z) else t;lt=z.low.idxmin() if len(z) else t;order='H_FIRST' if ht<lt else ('L_FIRST' if lt<ht else 'AMBIG')
  rec=dict(time=t,high=hi,low=lo,outside=outside,extreme_order=order,high_time=ht,low_time=lt);rows.append(rec);prev=rec
 return pd.DataFrame(rows).set_index('time') if rows else pd.DataFrame()

def confirm_st(h1,pivot,kind):
 start=pivot['high_time'] if kind==1 else pivot['low_time'];z=h1.loc[h1.index>=start];H=float(pivot['high']);L=float(pivot['low'])
 for t,r in z.iterrows():
  if kind==1:
   if float(r.high)>H and t>start:return None
   if float(r.low)<L:return t+pd.Timedelta(hours=1)
  else:
   if float(r.low)<L and t>start:return None
   if float(r.high)>H:return t+pd.Timedelta(hours=1)
 return None

def rich_mt(q,h1,sym):
 e=effective4(q,h1);st=[]
 if len(e)<3:ST_CACHE[sym]=pd.DataFrame();return pd.DataFrame()
 rr=e.reset_index().to_dict('records')
 for l,m,r in zip(rr[:-2],rr[1:-1],rr[2:]):
  hok=m['high']>l['high'] and m['high']>r['high'];lok=m['low']<l['low'] and m['low']<r['low']
  if m['outside'] or (hok and lok):
   if m['extreme_order']=='H_FIRST':lok=False
   elif m['extreme_order']=='L_FIRST':hok=False
   else:hok=lok=False
  if hok:
   ka=confirm_st(h1,m,1)
   if ka is not None:st.append(dict(kind=1,extreme_time=m['time'],price=m['high'],known_at=ka,bar_low=m['low'],bar_high=m['high'],outside=m['outside']))
  if lok:
   ka=confirm_st(h1,m,-1)
   if ka is not None:st.append(dict(kind=-1,extreme_time=m['time'],price=m['low'],known_at=ka,bar_low=m['low'],bar_high=m['high'],outside=m['outside']))
 s=pd.DataFrame(st).sort_values('extreme_time') if st else pd.DataFrame();ST_CACHE[sym]=s.copy()
 if s.empty:return pd.DataFrame()
 mts=[]
 for kind,g in s.groupby('kind'):
  a=g.sort_values('extreme_time').to_dict('records')
  for l,m,r in zip(a[:-2],a[1:-1],a[2:]):
   ok=(m['price']>l['price'] and m['price']>r['price']) if kind==1 else (m['price']<l['price'] and m['price']<r['price'])
   if not ok:continue
   A=float(q['atr'].asof(pd.Timestamp(m['extreme_time'])))
   if not np.isfinite(A) or A<=0:continue
   prom=((m['price']-max(l['price'],r['price']))/A) if kind==1 else ((min(l['price'],r['price'])-m['price'])/A)
   mts.append(dict(kind=kind,extreme_time=m['extreme_time'],level=float(m['price']),known_at=max(pd.Timestamp(l['known_at']),pd.Timestamp(m['known_at']),pd.Timestamp(r['known_at'])),mt_prom_atr=prom,outside=bool(m['outside'])))
 mt=pd.DataFrame(mts).sort_values('known_at') if mts else pd.DataFrame()
 if mt.empty:return mt
 prev=[]
 for _,r in mt.sort_values('extreme_time').iterrows():
  z=mt[(mt.kind==-int(r.kind))&(mt.extreme_time<r.extreme_time)];prev.append(float(z.iloc[-1].level) if len(z) else np.nan)
 mt=mt.sort_values('extreme_time').copy();mt['prev_opp_mt_level']=prev;return mt.sort_values('known_at')

def latest_st_anchor(sym,side,t):
 s=ST_CACHE.get(sym,pd.DataFrame());kind=-1 if side==1 else 1
 if s.empty:return np.nan
 z=s[(s.kind==kind)&(pd.to_datetime(s.known_at,utc=True)<=pd.Timestamp(t))];return float(z.iloc[-1].price) if len(z) else np.nan

def candidates(sym,x,q,mt):
 rows=[];idx=x.index
 if mt.empty:return pd.DataFrame()
 for kind,g in mt.groupby('kind'):
  g=g.sort_values('known_at').reset_index(drop=True)
  for j,r in g.iterrows():
   ka=pd.Timestamp(r.known_at);start=idx.searchsorted(ka,'left');end=len(x) if j+1==len(g) else idx.searchsorted(pd.Timestamp(g.loc[j+1,'known_at']),'left')
   if start>=end:continue
   A=float(q['atr'].asof(ka.floor('4h')));L=float(r.level)
   if not np.isfinite(A) or A<=0:continue
   seg=x.iloc[start:end];cside=1 if kind==1 else -1;cmask=(seg.close>=L+.10*A) if cside==1 else (seg.close<=L-.10*A);rside=-cside;rmask=((seg.high>=L-.05*A)&(seg.close<L)) if kind==1 else ((seg.low<=L+.05*A)&(seg.close>L))
   for route,side,mask in [('CONTINUATION',cside,cmask),('REJECTION',rside,rmask)]:
    hit=np.flatnonzero(mask.to_numpy())
    if not len(hit):continue
    i=start+int(hit[0])
    if i+1>=len(x):continue
    t=idx[i];pre=x.iloc[i-1] if i>0 else x.iloc[i];ev=x.iloc[i];entry=float(x.iloc[i+1].open);pa=float(r.prev_opp_mt_level) if np.isfinite(r.prev_opp_mt_level) else np.nan;swing=abs(L-pa) if np.isfinite(pa) else np.nan
    structural_target=(L+side*swing if route=='CONTINUATION' else pa+side*swing) if np.isfinite(swing) else np.nan;stop_anchor=L if route=='REJECTION' else latest_st_anchor(sym,side,t+pd.Timedelta(hours=1))
    rec=dict(symbol=sym,side=side,route=route,event_time=t,decision_time=t+pd.Timedelta(hours=1),entry_time=idx[i+1],entry=entry,level=L,atr4=A,mt_prom_atr=float(r.mt_prom_atr),level_age_h=(t-ka).total_seconds()/3600,stop_anchor=stop_anchor,structural_target=structural_target)
    for n in [3,6,12,24]:rec[f'pre_ret{n}_dir']=side*float(pre.get(f'ret{n}',np.nan))
    for n in [1,3,6,12]:rec[f'pre_taker{n}_dir']=side*float(pre.get(f'taker{n}',np.nan))
    rec.update(pre_ent24=float(pre.get('ent24',np.nan)),pre_eff6=float(pre.get('eff6',np.nan)),pre_vol_z72=float(pre.get('vol_z72',np.nan)),pre_count_z72=float(pre.get('count_z72',np.nan)),h4_ret1_dir=side*float(ev.get('h4_ret1',np.nan)))
    rec['oi_chg12']=float(ev.get('oi_chg12',np.nan));rec['top_acct_log_dir']=side*float(ev.get('log_count_toptrader_long_short_ratio',np.nan));rows.append(rec)
 return pd.DataFrame(rows).sort_values('entry_time') if rows else pd.DataFrame()

@dataclass(frozen=True)
class Cfg: family:str;buffer:float;horizon:int

def updates(sym,side,start,end):
 s=ST_CACHE.get(sym,pd.DataFrame());kind=-1 if side==1 else 1
 if s.empty:return []
 z=s[(s.kind==kind)&(pd.to_datetime(s.known_at,utc=True)>start)&(pd.to_datetime(s.known_at,utc=True)<=end)].sort_values('known_at');return [(pd.Timestamp(r.known_at),float(r.price)) for _,r in z.iterrows()]

def senior_trade(x,r,cfg):
 side=int(r.side);A=float(r.atr4);entry=float(r.entry);anchor=float(r.stop_anchor) if np.isfinite(r.stop_anchor) else float(r.level);stop=anchor-side*cfg.buffer*A;risk=side*(entry-stop)/A
 if not np.isfinite(risk) or risk<=0:return None
 i=x.index.searchsorted(pd.Timestamp(r.entry_time),'left');jend=min(len(x)-1,i+cfg.horizon);target=float(r.structural_target) if np.isfinite(r.structural_target) else np.nan
 if np.isfinite(target) and side*(target-entry)<=0:target=np.nan
 ups=updates(str(r.symbol),side,pd.Timestamp(r.entry_time),x.index[jend]);ui=0;active=stop;exitp=None;reason='TIME';j=i
 for j in range(i,jend+1):
  bt=x.index[j]
  while ui<len(ups) and ups[ui][0]<=bt:
   cand=ups[ui][1]-side*.10*A;active=max(active,cand) if side==1 else min(active,cand);ui+=1
  bar=x.iloc[j];hs=(float(bar.low)<=active) if side==1 else (float(bar.high)>=active)
  if hs:exitp=active;reason='STOP' if active==stop else 'ST_TRAIL';break
  if cfg.family in ('TARGET','HYBRID') and np.isfinite(target):
   ht=(float(bar.high)>=target) if side==1 else (float(bar.low)<=target)
   if ht:exitp=target;reason='WILLIAMS_TARGET';break
 if exitp is None:exitp=float(x.iloc[jend].close);j=jend
 gross=side*(exitp-entry)/entry
 return dict(exit_time=x.index[j],exit_price=exitp,gross_fraction=gross,reason=reason,risk_atr=float(risk))

def gate(sym,r):
 f=lambda v:np.isfinite(float(v));side=int(r.side);route=str(r.route)
 if sym=='BTCUSDT' and side==1 and route=='CONTINUATION':return f(r.top_acct_log_dir) and float(r.top_acct_log_dir)<=.451694 and f(r.pre_taker1_dir) and float(r.pre_taker1_dir)>=.0842562 and f(r.pre_vol_z72) and float(r.pre_vol_z72)<1.5 and f(r.pre_count_z72) and float(r.pre_count_z72)<1.5,Cfg('TRAIL',1.0,504),'BTC_LONG_CONT'
 if sym=='SOLUSDT' and side==-1 and route=='CONTINUATION':return f(r.oi_chg12) and float(r.oi_chg12)>=.0038566,Cfg('TARGET',0,336),'SOL_SHORT_CONT'
 if sym=='SOLUSDT' and side==-1 and route=='REJECTION':return f(r.pre_eff6) and float(r.pre_eff6)>=.775315,Cfg('TARGET',.25,168),'SOL_SHORT_REJ'
 if sym=='XRPUSDT' and side==-1 and route=='REJECTION':return f(r.pre_ent24) and float(r.pre_ent24)<=.954434,Cfg('TRAIL',1.0,336),'XRP_SHORT_REJ'
 return False,None,'NOT_ALLOWED'

def run_symbol(sym):
 print('LOAD',sym,flush=True);h=load_klines(sym,'1h','2020-09','2025-12');m=load_metrics_raw(sym);print('DATA',sym,len(h),len(m),str(m.index.min()),str(m.index.max()),flush=True)
 q=make4(h);x=enrich(h,q,m);mt=rich_mt(q,h,sym);e=candidates(sym,x,q,mt);rows=[]
 e=e[(pd.to_datetime(e.entry_time,utc=True)>=START)&(pd.to_datetime(e.entry_time,utc=True)<END)] if len(e) else e
 for _,r in e.iterrows():
  ok,cfg,gid=gate(sym,r)
  if not ok:continue
  z=senior_trade(x,r,cfg)
  if z is None:continue
  d=r.to_dict();d.update(z);d['module']='SENIOR_WILLIAMS';d['gate_id']=gid
  for bps in [12,16,20]:d[f'net{bps}_fraction']=float(z['gross_fraction'])-bps/10000
  rows.append(d)
 d=pd.DataFrame(rows);d.to_csv(OUT/f'senior_{sym}_2024_2025.csv',index=False)
 counts={str(y):int((pd.to_datetime(d.entry_time,utc=True).dt.year==y).sum()) if len(d) else 0 for y in [2024,2025]}
 print('SENIOR_YEAR_COUNTS',sym,json.dumps(counts,sort_keys=True),flush=True);return d,counts

def main():
 print('AIRM_SENIOR_ARCHIVE_REPLAY_START source_blob='+SOURCE_BLOB_SHA,flush=True)
 all_d=[];counts={}
 for s in ['BTCUSDT','SOLUSDT','XRPUSDT']:
  d,c=run_symbol(s);counts[s]=c
  if len(d):all_d.append(d)
 actual={s:counts[s]['2025'] for s in counts};expected={'BTCUSDT':4,'SOLUSDT':14,'XRPUSDT':3};ok=actual==expected
 print('SENIOR_2025_CONTROL',json.dumps({'expected':expected,'actual':actual,'pass':ok},sort_keys=True),flush=True)
 if all_d:pd.concat(all_d,ignore_index=True).sort_values('entry_time').to_csv(OUT/'senior_all_2024_2025.csv',index=False)
 (OUT/'summary.json').write_text(json.dumps({'source_blob':SOURCE_BLOB_SHA,'counts':counts,'control_2025':{'expected':expected,'actual':actual,'pass':ok}},indent=2),encoding='utf-8')
 if not ok:raise SystemExit(3)
 print('AIRM_SENIOR_ARCHIVE_REPLAY_PASS',flush=True)
if __name__=='__main__':main()
