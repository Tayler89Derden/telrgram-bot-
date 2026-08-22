#!/usr/bin/env python3
import io, json, zipfile
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd
import requests

SYMBOLS = ["BTCUSDT","SOLUSDT","XRPUSDT","ETHUSDT","LINKUSDT"]
TF = "15m"
START_MONTH = "2023-11"
END_MONTH = "2025-12"
OUT = Path("artifacts/expansion_2024_2025")
OUT.mkdir(parents=True, exist_ok=True)
RT_COST = 0.0016  # 16 bps round trip practical proxy
LOOKBACK = 96*30  # 30 days of 15m bars
COLS = ["open_time","open","high","low","close","volume","close_time","quote_volume","count","taker_buy_volume","taker_buy_quote_volume","ignore"]


def months_between(a,b):
    return [str(x) for x in pd.period_range(a,b,freq="M")]


def download_symbol(symbol):
    parts=[]
    sess=requests.Session()
    for ym in months_between(START_MONTH, END_MONTH):
        url=f"https://data.binance.vision/data/futures/um/monthly/klines/{symbol}/{TF}/{symbol}-{TF}-{ym}.zip"
        r=sess.get(url,timeout=60)
        if r.status_code != 200:
            raise RuntimeError(f"download failed {r.status_code} {url}")
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            names=z.namelist()
            if len(names)!=1:
                raise RuntimeError(f"unexpected zip members {symbol} {ym}: {names}")
            raw=z.read(names[0])
        df=pd.read_csv(io.BytesIO(raw),header=None,names=COLS)
        df["open_time"]=pd.to_numeric(df["open_time"],errors="coerce")
        df=df[df.open_time.notna()].copy()
        for c in ["open","high","low","close","volume","quote_volume","count","taker_buy_volume","taker_buy_quote_volume"]:
            df[c]=pd.to_numeric(df[c],errors="coerce")
        parts.append(df)
        print(f"DOWNLOAD {symbol} {ym} rows={len(df)}")
    df=pd.concat(parts,ignore_index=True)
    df["time"]=pd.to_datetime(df.open_time.astype("int64"),unit="ms",utc=True)
    return df.drop_duplicates("open_time").sort_values("open_time").reset_index(drop=True)


def features(df):
    x=df.copy()
    prev=x.close.shift(1)
    tr=np.maximum(x.high-x.low, np.maximum((x.high-prev).abs(), (x.low-prev).abs()))
    x["atr"]=tr.rolling(14,min_periods=14).mean()
    x["atr_pct"]=x.atr/x.close
    mid=x.close.rolling(20,min_periods=20).mean()
    std=x.close.rolling(20,min_periods=20).std(ddof=0)
    x["bbw"]=(4.0*std)/mid
    x["atr_q20"]=x.atr_pct.shift(1).rolling(LOOKBACK,min_periods=LOOKBACK//2).quantile(0.20)
    x["atr_q30"]=x.atr_pct.shift(1).rolling(LOOKBACK,min_periods=LOOKBACK//2).quantile(0.30)
    x["bbw_q20"]=x.bbw.shift(1).rolling(LOOKBACK,min_periods=LOOKBACK//2).quantile(0.20)
    x["bbw_q30"]=x.bbw.shift(1).rolling(LOOKBACK,min_periods=LOOKBACK//2).quantile(0.30)
    x["atr_prev"]=x.atr.shift(1)
    x["atr_pct_prev"]=x.atr_pct.shift(1)
    x["bbw_prev"]=x.bbw.shift(1)
    x["body_atr"]=(x.close-x.open).abs()/x.atr_prev
    medq=x.quote_volume.shift(1).rolling(96,min_periods=48).median()
    x["vol_ratio"]=x.quote_volume/medq
    x["taker_share"]=x.taker_buy_quote_volume/x.quote_volume.replace(0,np.nan)
    for n in [16,24,32]:
        x[f"prior_high_{n}"]=x.high.shift(1).rolling(n,min_periods=n).max()
        x[f"prior_low_{n}"]=x.low.shift(1).rolling(n,min_periods=n).min()
    return x


def signal_mask(x, comp, n, buffer_atr, body_min, confirm):
    if comp=="atr20":
        c=(x.atr_pct_prev <= x.atr_q20)
    elif comp=="bbw20":
        c=(x.bbw_prev <= x.bbw_q20)
    elif comp=="both30":
        c=(x.atr_pct_prev <= x.atr_q30) & (x.bbw_prev <= x.bbw_q30)
    else:
        raise ValueError(comp)
    hi=x[f"prior_high_{n}"]; lo=x[f"prior_low_{n}"]
    long=(x.close > hi + buffer_atr*x.atr_prev)
    short=(x.close < lo - buffer_atr*x.atr_prev)
    body=(x.body_atr >= body_min)
    long &= c & body; short &= c & body
    if confirm in ("vol","both"):
        v=(x.vol_ratio >= 1.5); long &= v; short &= v
    if confirm in ("taker","both"):
        long &= (x.taker_share >= 0.55); short &= (x.taker_share <= 0.45)
    side=np.zeros(len(x),dtype=np.int8)
    side[np.asarray(long.fillna(False))]=1
    side[np.asarray(short.fillna(False))]=-1
    return side


def simulate(x, side, sl_atr, tp_atr, horizon, symbol, config_id, year):
    # Same rules as v1, optimized to visit only actual signal indices.
    times=x.time.to_numpy(); years=x.time.dt.year.to_numpy(); op=x.open.to_numpy(float); hi=x.high.to_numpy(float); lo=x.low.to_numpy(float); cl=x.close.to_numpy(float); atr=x.atr_prev.to_numpy(float)
    N=len(x); out=[]; last_exit=-1
    idxs=np.flatnonzero((side!=0) & (years==year) & np.isfinite(atr) & (atr>0))
    for i in idxs:
        if i <= last_exit or i >= N-1:
            continue
        s=int(side[i]); entry_i=i+1
        if years[entry_i] != year:
            continue
        entry=float(op[entry_i]); a=float(atr[i])
        stop=entry - s*sl_atr*a; target=entry + s*tp_atr*a
        end=min(entry_i+horizon-1,N-1)
        exit_i=end; exit_px=float(cl[end]); reason="TIME"
        if s==1:
            stop_hits=np.flatnonzero(lo[entry_i:end+1] <= stop)
            tp_hits=np.flatnonzero(hi[entry_i:end+1] >= target)
        else:
            stop_hits=np.flatnonzero(hi[entry_i:end+1] >= stop)
            tp_hits=np.flatnonzero(lo[entry_i:end+1] <= target)
        sj=(entry_i+int(stop_hits[0])) if len(stop_hits) else None
        tj=(entry_i+int(tp_hits[0])) if len(tp_hits) else None
        if sj is not None and (tj is None or sj <= tj):
            exit_i=sj; exit_px=stop; reason="STOP_FIRST" if tj==sj else "STOP"
        elif tj is not None:
            exit_i=tj; exit_px=target; reason="TP"
        gross=s*(exit_px/entry-1.0); net=gross-RT_COST
        out.append({"config_id":config_id,"symbol":symbol,"year":year,"side":s,"signal_time":str(pd.Timestamp(times[i])),"entry_time":str(pd.Timestamp(times[entry_i])),"exit_time":str(pd.Timestamp(times[exit_i])),"entry":entry,"exit":exit_px,"atr":a,"reason":reason,"gross":gross,"net":net})
        last_exit=exit_i
    return out


def stats(trades):
    if not trades:
        return {"n":0,"wins":0,"wr":0.0,"sum_net":0.0,"mean_net":0.0,"pf":0.0,"maxdd":0.0}
    r=np.array([t["net"] for t in trades],float)
    pos=r[r>0].sum(); neg=-r[r<0].sum(); pf=float(pos/neg) if neg>0 else float("inf")
    eq=np.cumsum(r); peaks=np.maximum.accumulate(np.r_[0.0,eq]); dd=np.r_[0.0,eq]-peaks
    return {"n":len(r),"wins":int((r>0).sum()),"wr":float((r>0).mean()),"sum_net":float(r.sum()),"mean_net":float(r.mean()),"pf":pf,"maxdd":float(dd.min())}


def portfolio(trades, start=10000.0, margin_frac=0.05, leverage=5.0):
    events=[]
    for k,t in enumerate(trades):
        events.append((pd.Timestamp(t["entry_time"]),0,k)); events.append((pd.Timestamp(t["exit_time"]),1,k))
    events.sort(key=lambda q:(q[0],q[1]))
    bal=start; peak=start; maxdd=0.0; active={}; accepted=[]
    for tm,typ,k in events:
        t=trades[k]
        if typ==0:
            margin=bal*margin_frac; notional=margin*leverage
            reserved=sum(v[0] for v in active.values())
            if reserved+margin <= bal+1e-9: active[k]=(margin,notional)
        elif k in active:
            margin,notional=active.pop(k); pnl=notional*t["net"]; bal+=pnl
            accepted.append((tm,k,pnl,bal)); peak=max(peak,bal); maxdd=min(maxdd,bal/peak-1.0)
    wins=sum(1 for _,_,p,_ in accepted if p>0)
    return {"start":start,"end":bal,"return":bal/start-1,"accepted":len(accepted),"wins":wins,"wr":wins/len(accepted) if accepted else 0.0,"realized_dd":maxdd}


def cfg_name(c):
    return f"{c['comp']}_r{c['range_n']}_b{c['buffer']}_body{c['body']}_{c['confirm']}_sl{c['sl']}_tp{c['tp']}_h{c['h']}"


def main():
    data={}
    for s in SYMBOLS:
        data[s]=features(download_symbol(s))
        data[s].to_csv(OUT/f"{s}_features.csv.gz",index=False,compression="gzip")
        print(f"FEATURES {s} rows={len(data[s])}")

    configs=[]
    for comp,range_n,buffer,body,confirm,exitp in product(["atr20","bbw20","both30"],[16,24,32],[0.0,0.10],[0.25,0.50],["none","vol","taker","both"],[(0.75,2.0,96),(1.0,2.0,96),(1.0,3.0,192)]):
        sl,tp,h=exitp; c={"comp":comp,"range_n":range_n,"buffer":buffer,"body":body,"confirm":confirm,"sl":sl,"tp":tp,"h":h}; c["id"]=cfg_name(c); configs.append(c)
    print(f"CONFIG_COUNT {len(configs)}")

    rows=[]; trade_cache={}
    for ci,c in enumerate(configs):
        agg={2024:[],2025:[]}; per={}
        for s in SYMBOLS:
            x=data[s]; side=signal_mask(x,c["comp"],c["range_n"],c["buffer"],c["body"],c["confirm"])
            for y in [2024,2025]:
                tr=simulate(x,side,c["sl"],c["tp"],c["h"],s,c["id"],y)
                per[(s,y)]=tr; agg[y].extend(tr); rows.append({"config_id":c["id"],"scope":s,"year":y,**c,**stats(tr)})
        for y in [2024,2025]: rows.append({"config_id":c["id"],"scope":"ALL","year":y,**c,**stats(agg[y])})
        trade_cache[c["id"]]=per
        if (ci+1)%40==0: print(f"TESTED {ci+1}/{len(configs)}")

    res=pd.DataFrame(rows); res.to_csv(OUT/"all_config_stats.csv",index=False)
    tr24=res[(res.scope=="ALL")&(res.year==2024)&(res.n>=40)].copy()
    if tr24.empty: raise RuntimeError("no configs satisfy universal min trade count")
    tr24["risk_score"]=tr24.sum_net + tr24.maxdd
    picks=[("MAX_TOTAL_NET",tr24.sort_values(["sum_net","pf"],ascending=False).iloc[0]),("MAX_PF",tr24.replace([np.inf,-np.inf],np.nan).dropna(subset=["pf"]).sort_values(["pf","sum_net"],ascending=False).iloc[0]),("RISK_ADJUSTED",tr24.sort_values(["risk_score","sum_net"],ascending=False).iloc[0])]
    seen=set(); universal=[]
    for label,row in picks:
        if row.config_id not in seen: seen.add(row.config_id); universal.append((label,row.config_id))

    summary={"method":{"timeframe":TF,"train_year":2024,"oos_year":2025,"rt_cost":RT_COST,"entry":"next-bar-open","intrabar_collision":"STOP_FIRST","configs_tested":len(configs)},"universal":[],"asset_specific":[]}
    all_selected_trades=[]
    for label,cid in universal:
        item={"selection":label,"config_id":cid,"train_2024":{},"oos_2025":{},"by_asset":{}}
        for y,key in [(2024,"train_2024"),(2025,"oos_2025")]:
            trs=[]
            for s in SYMBOLS: trs += trade_cache[cid][(s,y)]
            item[key]=stats(trs); item[key]["portfolio_5pct_x5"]=portfolio(trs)
            if y==2025: all_selected_trades += [{**t,"selection":label} for t in trs]
        for s in SYMBOLS: item["by_asset"][s]={"2024":stats(trade_cache[cid][(s,2024)]),"2025":stats(trade_cache[cid][(s,2025)])}
        summary["universal"].append(item)

    specialized_trades_24=[]; specialized_trades_25=[]
    for s in SYMBOLS:
        z=res[(res.scope==s)&(res.year==2024)&(res.n>=10)].sort_values(["sum_net","pf"],ascending=False)
        if z.empty:
            summary["asset_specific"].append({"symbol":s,"status":"NO_2024_CONFIG_WITH_10_TRADES"}); continue
        cid=z.iloc[0].config_id; t24=trade_cache[cid][(s,2024)]; t25=trade_cache[cid][(s,2025)]
        specialized_trades_24 += t24; specialized_trades_25 += t25
        summary["asset_specific"].append({"symbol":s,"config_id":cid,"train_2024":stats(t24),"oos_2025":stats(t25)})
    summary["asset_specific_portfolio"]={"2024":portfolio(specialized_trades_24),"2025":portfolio(specialized_trades_25)}

    with open(OUT/"summary.json","w") as f: json.dump(summary,f,indent=2,allow_nan=True)
    pd.DataFrame(all_selected_trades).to_csv(OUT/"selected_universal_oos_trades.csv",index=False)
    pd.DataFrame(specialized_trades_25).to_csv(OUT/"asset_specific_oos_trades.csv",index=False)
    print("EXPANSION_RESEARCH_SUMMARY"); print(json.dumps(summary,indent=2,allow_nan=True)); print("EXPANSION_RESEARCH_PASS")

if __name__=="__main__": main()
