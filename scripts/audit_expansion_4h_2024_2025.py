#!/usr/bin/env python3
import io, json, zipfile
from pathlib import Path
import numpy as np
import pandas as pd
import requests

SYMBOLS=["BTCUSDT","SOLUSDT","XRPUSDT","ETHUSDT","LINKUSDT"]
MONTHS=[str(x) for x in pd.period_range("2023-11","2025-12",freq="M")]
OUT=Path("artifacts/expansion_4h_audit"); OUT.mkdir(parents=True,exist_ok=True)
RT_COST=0.0016
COLS=["open_time","open","high","low","close","volume","close_time","quote_volume","count","taker_buy_volume","taker_buy_quote_volume","ignore"]

def download_4h(symbol):
    parts=[]; sess=requests.Session()
    for ym in MONTHS:
        url=f"https://data.binance.vision/data/futures/um/monthly/klines/{symbol}/4h/{symbol}-4h-{ym}.zip"
        r=sess.get(url,timeout=60); r.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            raw=z.read(z.namelist()[0])
        d=pd.read_csv(io.BytesIO(raw),header=None,names=COLS)
        d["open_time"]=pd.to_numeric(d["open_time"],errors="coerce")
        d=d[d.open_time.notna()].copy()
        for c in ["open","high","low","close","volume","quote_volume","taker_buy_quote_volume"]:
            d[c]=pd.to_numeric(d[c],errors="coerce")
        parts.append(d)
    x=pd.concat(parts,ignore_index=True).drop_duplicates("open_time").sort_values("open_time").reset_index(drop=True)
    x["time"]=pd.to_datetime(x.open_time.astype("int64"),unit="ms",utc=True)
    return x

def features(x,lookback=360,range_bars=6):
    x=x.copy(); prev=x.close.shift(1)
    tr=np.maximum(x.high-x.low,np.maximum((x.high-prev).abs(),(x.low-prev).abs()))
    x["atr"]=tr.rolling(14,min_periods=14).mean()
    mid=x.close.rolling(20,min_periods=20).mean(); std=x.close.rolling(20,min_periods=20).std(ddof=0)
    x["bbw"]=4*std/mid
    x["atr_prev"]=x.atr.shift(1); x["bbw_prev"]=x.bbw.shift(1)
    x["bbw_q10_60d"]=x.bbw.shift(1).rolling(lookback,min_periods=lookback//2).quantile(.10)
    x["prior_high_24h"]=x.high.shift(1).rolling(range_bars,min_periods=range_bars).max()
    x["prior_low_24h"]=x.low.shift(1).rolling(range_bars,min_periods=range_bars).min()
    x["body_atr"]=(x.close-x.open).abs()/x.atr_prev
    return x

def sides(x):
    comp=x.bbw_prev<=x.bbw_q10_60d
    long=(x.close>x.prior_high_24h+0.10*x.atr_prev)&comp&(x.body_atr>=0.25)
    short=(x.close<x.prior_low_24h-0.10*x.atr_prev)&comp&(x.body_atr>=0.25)
    s=np.zeros(len(x),dtype=np.int8)
    s[np.asarray(long.fillna(False))]=1; s[np.asarray(short.fillna(False))]=-1
    return s

def simulate(x,side,year,symbol):
    times=x.time.to_numpy(); op=x.open.to_numpy(float); hi=x.high.to_numpy(float); lo=x.low.to_numpy(float); cl=x.close.to_numpy(float); atr=x.atr_prev.to_numpy(float)
    out=[]; i=0; N=len(x)
    while i<N-1:
        if side[i]==0 or pd.Timestamp(times[i]).year!=year or not np.isfinite(atr[i]) or atr[i]<=0:
            i+=1; continue
        s=int(side[i]); ei=i+1
        if pd.Timestamp(times[ei]).year!=year:
            i+=1; continue
        entry=float(op[ei]); a=float(atr[i]); stop=entry-s*a; target=entry+s*3*a
        end=min(ei+47,N-1); exi=end; expx=float(cl[end]); reason="TIME"
        for j in range(ei,end+1):
            if s==1: sh=lo[j]<=stop; th=hi[j]>=target
            else: sh=hi[j]>=stop; th=lo[j]<=target
            if sh and th: exi=j; expx=stop; reason="STOP_FIRST"; break
            if sh: exi=j; expx=stop; reason="STOP"; break
            if th: exi=j; expx=target; reason="TP"; break
        gross=s*(expx/entry-1.0); net=gross-RT_COST
        out.append({"symbol":symbol,"side":s,"signal_time":str(pd.Timestamp(times[i])),"entry_time":str(pd.Timestamp(times[ei])),"exit_time":str(pd.Timestamp(times[exi])),"entry":entry,"exit":expx,"atr":a,"reason":reason,"gross":gross,"net":net})
        i=exi+1
    return out

def stats(tr):
    r=np.array([t["net"] for t in tr],float)
    if len(r)==0:return {"n":0,"wins":0,"wr":0,"sum_net":0,"pf":0}
    pos=r[r>0].sum(); neg=-r[r<0].sum()
    return {"n":len(r),"wins":int((r>0).sum()),"wr":float((r>0).mean()),"sum_net":float(r.sum()),"pf":float(pos/neg) if neg else float("inf")}

def portfolio(tr,start=10000.0,margin_frac=.05,leverage=5.0):
    events=[]
    for k,t in enumerate(tr):
        events.append((pd.Timestamp(t["entry_time"]),0,k)); events.append((pd.Timestamp(t["exit_time"]),1,k))
    events.sort(key=lambda z:(z[0],z[1]))
    bal=start; peak=start; dd=0.; active={}; accepted=[]
    for tm,typ,k in events:
        if typ==0:
            margin=bal*margin_frac; notional=margin*leverage
            if sum(v[0] for v in active.values())+margin<=bal+1e-9: active[k]=(margin,notional)
        elif k in active:
            margin,notional=active.pop(k); pnl=notional*tr[k]["net"]; bal+=pnl
            peak=max(peak,bal); dd=min(dd,bal/peak-1.0); accepted.append((k,pnl))
    return {"start":start,"end":bal,"return":bal/start-1,"accepted":len(accepted),"wins":sum(p>0 for _,p in accepted),"realized_dd":dd}

def main():
    data={}; coverage={}
    for s in SYMBOLS:
        x=features(download_4h(s)); data[s]=x
        expected=pd.date_range("2023-11-01 00:00","2025-12-31 20:00",freq="4h",tz="UTC")
        coverage[s]={"rows":len(x),"expected":len(expected),"missing":len(expected.difference(x.time)),"duplicates":int(x.time.duplicated().sum())}
    byyear={}; alltr=[]
    for y in [2024,2025]:
        tr=[]; byasset={}
        for s,x in data.items():
            tt=simulate(x,sides(x),y,s); tr+=tt; byasset[s]={"stats":stats(tt),"portfolio":portfolio(tt)}
        byyear[str(y)]={"stats":stats(tr),"portfolio":portfolio(tr),"by_asset":byasset}; alltr+=tr
    short24=[t for t in alltr if t["side"]==-1 and pd.Timestamp(t["entry_time"]).year==2024]
    short25=[t for t in alltr if t["side"]==-1 and pd.Timestamp(t["entry_time"]).year==2025]
    summary={"contract":{"timeframe":"4h","bbw_period":20,"bbw_percentile":0.10,"percentile_lookback_bars":360,"percentile_lookback_days":60,"range_bars":6,"range_hours":24,"buffer_atr":0.10,"body_atr_min":0.25,"entry":"next_4h_open","sl_atr":1.0,"tp_atr":3.0,"max_hold_bars":48,"max_hold_days":8,"rt_cost":RT_COST,"collision":"STOP_FIRST"},"coverage":coverage,"years":byyear,"continuous":portfolio(alltr),"short_only":{"2024":{"stats":stats(short24),"portfolio":portfolio(short24)},"2025":{"stats":stats(short25),"portfolio":portfolio(short25)},"continuous":portfolio(short24+short25)}}
    pd.DataFrame(alltr).to_csv(OUT/"trades.csv",index=False)
    json.dump(summary,open(OUT/"summary.json","w"),indent=2,sort_keys=True)
    print(json.dumps(summary,indent=2,sort_keys=True))

if __name__=="__main__":main()
