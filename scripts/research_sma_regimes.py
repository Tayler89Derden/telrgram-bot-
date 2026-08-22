#!/usr/bin/env python3
from __future__ import annotations
import io, json, zipfile, hashlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np
import pandas as pd
import requests

ASSETS=['BTCUSDT','SOLUSDT','XRPUSDT','ETHUSDT','LINKUSDT']
EVAL_START=pd.Timestamp('2022-01-01',tz='UTC')
EVAL_END=pd.Timestamp('2026-08-21',tz='UTC')  # end-exclusive; last completed day 2026-08-20
WARMUP_START='2021-01'
MONTHLY_END='2026-07'
DAILY_AUG=pd.date_range('2026-08-01','2026-08-20',freq='D',tz='UTC')
KCOL=['open_time','open','high','low','close','volume','close_time','quote_volume','count','taker_buy_volume','taker_buy_quote_volume','ignore']
OUT=Path('artifacts/sma_research'); OUT.mkdir(parents=True,exist_ok=True)


def months(a,b):
    y,m=map(int,a.split('-')); y2,m2=map(int,b.split('-'))
    while (y,m)<=(y2,m2):
        yield f'{y:04d}-{m:02d}'
        m+=1
        if m==13: y+=1; m=1


def getzip(url,timeout=35):
    try:
        r=requests.get(url,timeout=timeout)
        if r.status_code!=200: return None
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            return z.read(z.namelist()[0])
    except Exception:
        return None


def parse_kline(raw):
    x=pd.read_csv(io.BytesIO(raw))
    norm=str(x.columns[0]).strip().lower().replace(' ','_') if len(x.columns) else ''
    if len(x.columns)!=12 or norm!='open_time':
        x=pd.read_csv(io.BytesIO(raw),header=None,names=KCOL)
    else:
        x.columns=KCOL
    for c in KCOL:
        x[c]=pd.to_numeric(x[c],errors='coerce')
    x=x.dropna(subset=['open_time','open','high','low','close'])
    ot=x.open_time.astype('int64').to_numpy()
    ot=np.where(ot>10**14,ot//1000,ot)
    x['time']=pd.to_datetime(ot,unit='ms',utc=True)
    return x.set_index('time')


def load_asset(sym):
    urls=[]
    for ym in months(WARMUP_START,MONTHLY_END):
        urls.append(f'https://data.binance.vision/data/futures/um/monthly/klines/{sym}/1d/{sym}-1d-{ym}.zip')
    for dt in DAILY_AUG:
        urls.append(f'https://data.binance.vision/data/futures/um/daily/klines/{sym}/1d/{sym}-1d-{dt:%Y-%m-%d}.zip')
    arr=[]; misses=0
    with ThreadPoolExecutor(max_workers=20) as ex:
        for raw in ex.map(getzip,urls):
            if raw is None:
                misses+=1; continue
            try: arr.append(parse_kline(raw))
            except Exception: misses+=1
    if not arr: raise RuntimeError(f'NO_DATA {sym}')
    d=pd.concat(arr).sort_index(); d=d[~d.index.duplicated(keep='last')]
    d=d[['open','high','low','close','volume','quote_volume','count']].copy()
    print('ASSET_DATA',sym,len(d),d.index.min(),d.index.max(),'misses',misses,flush=True)
    return d


def features(sym,d):
    z=d.copy(); z['symbol']=sym
    pc=z.close.shift(1)
    tr=np.maximum(z.high-z.low,np.maximum((z.high-pc).abs(),(z.low-pc).abs()))
    z['atr14']=tr.rolling(14,min_periods=14).mean()
    for n in [20,40,60]:
        z[f'sma{n}']=z.close.rolling(n,min_periods=n).mean()
        z[f'slope{n}_5']=z[f'sma{n}']/z[f'sma{n}'].shift(5)-1
        z[f'dist{n}_pct']=z.close/z[f'sma{n}']-1
        z[f'dist{n}_atr']=(z.close-z[f'sma{n}'])/z.atr14.replace(0,np.nan)
    z['bull_stack']=(z.sma20>z.sma40)&(z.sma40>z.sma60)
    z['bear_stack']=(z.sma20<z.sma40)&(z.sma40<z.sma60)
    z['bull_confirm']=z.bull_stack&(z.slope60_5>0)
    z['bear_confirm']=z.bear_stack&(z.slope60_5<0)
    z['above60']=z.close>z.sma60
    z['below60']=z.close<z.sma60
    z['slow_bull']=(z.close>z.sma60)&(z.slope60_5>0)
    z['slow_bear']=(z.close<z.sma60)&(z.slope60_5<0)
    z['cross20_60_up']=(z.sma20>z.sma60)&(z.sma20.shift(1)<=z.sma60.shift(1))
    z['cross20_60_dn']=(z.sma20<z.sma60)&(z.sma20.shift(1)>=z.sma60.shift(1))
    z['cross_price20_up']=(z.close>z.sma20)&(z.close.shift(1)<=z.sma20.shift(1))
    z['cross_price20_dn']=(z.close<z.sma20)&(z.close.shift(1)>=z.sma20.shift(1))
    for h in [1,5,10,20]:
        z[f'fwd{h}']=z.close.shift(-h)/z.close-1
    return z[(z.index>=EVAL_START)&(z.index<EVAL_END)].copy()


def stat_rows(z):
    rows=[]
    states={
      'ALL':pd.Series(True,index=z.index),
      'ABOVE_SMA20':z.close>z.sma20,
      'BELOW_SMA20':z.close<z.sma20,
      'ABOVE_SMA40':z.close>z.sma40,
      'BELOW_SMA40':z.close<z.sma40,
      'ABOVE_SMA60':z.above60,
      'BELOW_SMA60':z.below60,
      'SLOW_BULL_close>sma60_slope60+':z.slow_bull,
      'SLOW_BEAR_close<sma60_slope60-':z.slow_bear,
      'BULL_STACK_20>40>60':z.bull_stack,
      'BEAR_STACK_20<40<60':z.bear_stack,
      'BULL_CONFIRM_stack+slope60+':z.bull_confirm,
      'BEAR_CONFIRM_stack+slope60-':z.bear_confirm,
      'EXTREME_ABOVE_SMA20_2ATR':z.dist20_atr>=2,
      'EXTREME_BELOW_SMA20_2ATR':z.dist20_atr<=-2,
      'EXTREME_ABOVE_SMA60_2ATR':z.dist60_atr>=2,
      'EXTREME_BELOW_SMA60_2ATR':z.dist60_atr<=-2,
    }
    for name,mask in states.items():
        q=z[mask.fillna(False)]
        for h in [1,5,10,20]:
            s=q[f'fwd{h}'].dropna()
            if len(s)==0: continue
            rows.append(dict(symbol=z.symbol.iloc[0],state=name,horizon_days=h,n=len(s),mean_return=float(s.mean()),median_return=float(s.median()),p_up=float((s>0).mean()),p_down=float((s<0).mean())))
    return rows


def event_rows(z):
    rows=[]
    events={
      'SMA20_CROSS_SMA60_UP':z.cross20_60_up,
      'SMA20_CROSS_SMA60_DOWN':z.cross20_60_dn,
      'PRICE_CROSS_SMA20_UP':z.cross_price20_up,
      'PRICE_CROSS_SMA20_DOWN':z.cross_price20_dn,
    }
    for name,mask in events.items():
        q=z[mask.fillna(False)]
        direction=1 if name.endswith('UP') else -1
        for h in [1,5,10,20]:
            s=q[f'fwd{h}'].dropna()
            if len(s)==0: continue
            ds=direction*s
            rows.append(dict(symbol=z.symbol.iloc[0],event=name,horizon_days=h,n=len(s),mean_raw_return=float(s.mean()),median_raw_return=float(s.median()),directional_mean=float(ds.mean()),directional_hit=float((ds>0).mean())))
    return rows


def latest_row(z):
    r=z.dropna(subset=['sma60']).iloc[-1]
    return dict(symbol=r.symbol,date=r.name.isoformat(),close=float(r.close),sma20=float(r.sma20),sma40=float(r.sma40),sma60=float(r.sma60),slope20_5=float(r.slope20_5),slope40_5=float(r.slope40_5),slope60_5=float(r.slope60_5),dist20_atr=float(r.dist20_atr),dist40_atr=float(r.dist40_atr),dist60_atr=float(r.dist60_atr),bull_stack=bool(r.bull_stack),bear_stack=bool(r.bear_stack),slow_bull=bool(r.slow_bull),slow_bear=bool(r.slow_bear))


def main():
    allf=[]; stats=[]; events=[]; latest=[]
    for sym in ASSETS:
        d=load_asset(sym); z=features(sym,d)
        allf.append(z.reset_index().rename(columns={'time':'date'}))
        stats.extend(stat_rows(z)); events.extend(event_rows(z)); latest.append(latest_row(z))
    f=pd.concat(allf,ignore_index=True)
    f.to_csv(OUT/'daily_sma_features_2022_2026.csv.gz',index=False,compression='gzip')
    pd.DataFrame(stats).to_csv(OUT/'sma_state_summary.csv',index=False)
    pd.DataFrame(events).to_csv(OUT/'sma_event_summary.csv',index=False)
    pd.DataFrame(latest).to_csv(OUT/'sma_latest_2026-08-20.csv',index=False)
    manifest={'assets':ASSETS,'eval_start':str(EVAL_START),'eval_end_exclusive':str(EVAL_END),'rows':int(len(f)),'files':{}}
    for p in sorted(OUT.iterdir()):
        manifest['files'][p.name]={'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('AIRM_SMA_RESEARCH_PASS',json.dumps(manifest),flush=True)
    print(pd.DataFrame(latest).to_string(index=False),flush=True)

if __name__=='__main__': main()
