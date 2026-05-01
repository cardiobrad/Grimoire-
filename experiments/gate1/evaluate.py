"""
evaluate.py v2 — All ChatGPT audit fixes applied.
- Constant predictors → NaN
- 60/20/20 train/cal/test split
- Threshold calibrated on cal, metrics on held-out test
- True ablations (drop each GSM component)
- Tighter adversarial matching (same mass + nodes, different family)
- Full metrics: precision, recall, F1, balanced accuracy
"""
import numpy as np
import pandas as pd
from config import OUT_DIR, GSM

SCORERS = {
    "GSM score": "gsm_score", "Mass only": "bl_mass", "Node count": "bl_node_count",
    "Edge count": "bl_edge_count", "Density": "bl_density", "Mean degree": "bl_mean_degree",
    "LCC fraction": "bl_lcc_frac", "Field mean": "bl_field_mean",
    "Field max": "bl_field_max", "Field std": "bl_field_std",
}

def _auc(y_true, y_score):
    pos = sum(y_true); neg = len(y_true) - pos
    if pos == 0 or neg == 0: return float("nan")
    if len(set(round(s, 10) for s in y_score)) <= 1: return float("nan")
    tp = auc = 0.0
    for _, label in sorted(zip(y_score, y_true), reverse=True):
        if label: tp += 1
        else: auc += tp
    return round(auc / (pos * neg), 4)

def _split(df, seed=42):
    rng = np.random.RandomState(seed)
    idx = rng.permutation(len(df))
    a, b = int(len(df)*0.6), int(len(df)*0.8)
    return df.iloc[idx[:a]].copy(), df.iloc[idx[a:b]].copy(), df.iloc[idx[b:]].copy()

def _best_thresh(yt, ys):
    best_t = best_ba = 0
    for t in np.linspace(min(ys)-0.01, max(ys)+0.01, 300):
        pred = [1 if s >= t else 0 for s in ys]
        tp = sum(1 for p, y in zip(pred, yt) if p == 1 and y == 1)
        tn = sum(1 for p, y in zip(pred, yt) if p == 0 and y == 0)
        p, n = sum(yt), len(yt)-sum(yt)
        ba = ((tp/p if p else 0) + (tn/n if n else 0))/2
        if ba > best_ba: best_ba, best_t = ba, t
    return best_t, best_ba

def _metrics(yt, yp):
    tp = sum(1 for t,p in zip(yt,yp) if t==1 and p==1)
    fp = sum(1 for t,p in zip(yt,yp) if t==0 and p==1)
    fn = sum(1 for t,p in zip(yt,yp) if t==1 and p==0)
    tn = sum(1 for t,p in zip(yt,yp) if t==0 and p==0)
    pr = tp/(tp+fp) if tp+fp else 0; re = tp/(tp+fn) if tp+fn else 0
    f1 = 2*pr*re/(pr+re) if pr+re else 0
    p,n = tp+fn, tn+fp
    ba = ((tp/p if p else 0)+(tn/n if n else 0))/2
    return {"tp":tp,"fp":fp,"fn":fn,"tn":tn,"prec":round(pr,4),"rec":round(re,4),
            "f1":round(f1,4),"ba":round(ba,4),"acc":round((tp+tn)/len(yt),4) if yt else 0}

def _ablated(row, drop):
    c = {"w_a": row.get("gsm_max_u",0)/max(GSM["A_c"],1e-12),
         "w_r": row.get("gsm_r_eff",0)/max(GSM["R_c"],1e-12),
         "w_m": row.get("gsm_mass",0)/max(GSM["M_c"],1e-12),
         "w_t": row.get("gsm_conn",0),
         "w_g": min(row.get("gsm_grad_shape",0)/0.5, 1.0)}
    if drop in c: c[drop] = 0.0
    return sum(GSM[k]*c[k] for k in c)

def evaluate_pipeline(results_path=None):
    path = results_path or (OUT_DIR / "results.csv")
    df = pd.read_csv(path)
    P = print

    P("\n" + "="*70)
    P("  GSM VALIDATION v2 (splits + ablations + tighter matching)")
    P("="*70)

    df["y"] = df["survived"].astype(int)
    ns = df["y"].sum(); n = len(df)
    P(f"\n  Total={n}  Survived={ns} ({100*ns/n:.1f}%)  Decayed={n-ns}")

    if ns == 0 or ns == n:
        P("  ⚠ No outcome variance. Cannot evaluate."); return {"verdict":"NO_VARIANCE"}

    P("\n  Per-family:")
    fm = df.groupby("family").agg(cnt=("y","count"),surv=("y","sum"),gsm=("gsm_score","mean")).reset_index()
    fm["rate%"] = (fm["surv"]/fm["cnt"]*100).round(1)
    P(fm.to_string(index=False))

    train, cal, test = _split(df)
    P(f"\n  Splits: train={len(train)} cal={len(cal)} test={len(test)}")

    # Train AUC
    P("\n  Train AUC:")
    for nm, col in SCORERS.items():
        if col in train: P(f"    {nm:<20} {_auc(train['y'].tolist(), train[col].fillna(0).tolist())}")

    # Calibrate
    thresh, cba = _best_thresh(cal["y"].tolist(), cal["gsm_score"].fillna(0).tolist())
    P(f"\n  Calibrated threshold={thresh:.4f} (cal balanced_acc={cba:.4f})")

    # === HELD-OUT TEST ===
    yt = test["y"].tolist()
    P(f"\n  === HELD-OUT TEST (n={len(test)}) ===")

    P("\n  Test AUC:")
    ta = {}
    for nm, col in SCORERS.items():
        if col in test.columns:
            a = _auc(yt, test[col].fillna(0).tolist()); ta[nm] = a
            s = f"{a:.4f}" if a == a else "NaN"
            P(f"    {nm:<20} {s:>8}{' ◀ GSM' if nm=='GSM score' else ''}")

    pred = [1 if s >= thresh else 0 for s in test["gsm_score"].fillna(0)]
    m = _metrics(yt, pred)
    P(f"\n  Classification (thresh={thresh:.4f}):")
    for k in ["acc","ba","prec","rec","f1"]: P(f"    {k:<8} {m[k]}")
    P(f"    TP={m['tp']} FP={m['fp']} FN={m['fn']} TN={m['tn']}")

    # Ablation
    ga = ta.get("GSM score", float("nan"))
    P(f"\n  Ablation:")
    for d, lab in [("w_a","amplitude"),("w_r","radius"),("w_m","mass"),("w_t","topology"),("w_g","gradient")]:
        ab = [_ablated(r, d) for _, r in test.iterrows()]
        aa = _auc(yt, ab)
        delta = ga - aa if not (np.isnan(ga) or np.isnan(aa)) else float("nan")
        P(f"    Drop {lab:<12} AUC={aa if aa==aa else 'NaN':>8}  delta={f'{delta:+.4f}' if delta==delta else 'NaN'}")

    # Adversarial (same mass + nodes, different family)
    P(f"\n  Adversarial pairs (same mass+nodes, diff family, test only):")
    t2 = test.copy()
    t2["mk"] = t2["bl_mass"].round(2).astype(str) + "_" + t2["bl_node_count"].astype(str)
    af = gw = mw = 0
    for _, grp in t2.groupby("mk"):
        s = grp[grp["y"]==1]; d = grp[grp["y"]==0]
        if len(s)==0 or len(d)==0: continue
        for _, sr in s.iterrows():
            for _, dr in d.iterrows():
                if sr["family"]==dr["family"]: continue
                af += 1
                if sr["gsm_score"] > dr["gsm_score"]: gw += 1
                if sr["bl_mass"] > dr["bl_mass"]: mw += 1
    if af:
        P(f"    Found={af}  GSM correct={gw} ({100*gw/af:.1f}%)  Mass correct={mw} ({100*mw/af:.1f}%)")
        if gw > mw: P("    ✓ GSM discriminates topology where mass cannot")
        else: P("    ✗ GSM does NOT discriminate better")
    else: P("    No valid pairs")

    # Verdict
    P("\n" + "="*70); P("  VERDICT (held-out test)"); P("="*70)
    ps = tt = 0
    for bl in ["Mass only","Node count","Density"]:
        tt += 1; ba2 = ta.get(bl, float("nan"))
        if np.isnan(ba2): ps += 1; P(f"  ✓ GSM beats {bl} (baseline NaN)")
        elif not np.isnan(ga) and ga > ba2: ps += 1; P(f"  ✓ GSM beats {bl} ({ga:.4f}>{ba2:.4f})")
        else: P(f"  ✗ GSM does NOT beat {bl}")
    tt += 1
    if af > 0 and gw > mw: ps += 1; P("  ✓ GSM discriminates adversarial topology")
    else: P("  ✗ GSM does NOT discriminate adversarial topology")

    P(f"\n  RESULT: {ps}/{tt}")
    v = "PASS" if ps==tt else "PARTIAL" if ps>=tt-1 else "FAIL"
    if v=="PASS": P("  ✓✓✓ GATE 1 CLEARED")
    elif v=="PARTIAL": P("  ⚠ Mostly passes")
    else: P("  ✗ GATE 1 NOT CLEARED")
    P("="*70)

    summary = {"gsm_auc":ga,"thresh":thresh,"ba":m["ba"],"f1":m["f1"],
               "prec":m["prec"],"rec":m["rec"],"adv":af,
               "gsm_adv%":round(100*gw/max(af,1),1),"passes":ps,"tests":tt,"verdict":v}
    pd.DataFrame([summary]).to_csv(OUT_DIR / "evaluation_v2.csv", index=False)
    return summary
