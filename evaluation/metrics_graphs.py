"""Read predictions, compute metrics, save graphs + tables."""
import argparse, json, os
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import (precision_recall_fscore_support, accuracy_score,
                             confusion_matrix, matthews_corrcoef, classification_report)

p = argparse.ArgumentParser()
p.add_argument("--data", required=True); p.add_argument("--pred", required=True)
p.add_argument("--name", required=True, help="tag for output files, e.g. synthetic")
a = p.parse_args()
os.makedirs("graphs", exist_ok=True); os.makedirs("results", exist_ok=True)
CLASSES = ["safe", "race_condition", "deadlock", "concurrency_issue"]

def flatten(o):
    if isinstance(o, dict): return " ".join(flatten(v) for v in o.values())
    if isinstance(o, list): return " ".join(flatten(v) for v in o)
    return str(o)

def find_list(o):
    """first list found in the response (the bug list), or None"""
    if isinstance(o, list): return o
    if isinstance(o, dict):
        for v in o.values():
            r = find_list(v)
            if r is not None: return r
    return None

def to_label(resp):
    if resp is None: return None
    # our own backend returns an explicit "verdict" field
    if isinstance(resp, dict) and resp.get("verdict") in CLASSES:
        return resp["verdict"]
    lst = find_list(resp)
    if lst is not None and len(lst) == 0: return "safe"
    t = flatten(resp).lower()
    if "deadlock" in t: return "deadlock"
    if "race" in t or "data race" in t: return "race_condition"
    if lst is not None and len(lst) > 0: return "concurrency_issue"
    if any(k in t for k in ["no issue", "no bug", "no concurrency", "no problem", "safe"]): return "safe"
    if any(k in t for k in ["visibility", "atomic", "synchroniz", "lock", "wait", "notify", "volatile", "concurren"]): return "concurrency_issue"
    return "safe"

data = pd.read_csv(a.data)
pred = pd.DataFrame([json.loads(l) for l in open(a.pred, encoding="utf-8")])
df = data.merge(pred, on="uid")
n_err = int(df.response.isna().sum())
df["pred4"] = df.response.apply(to_label)
df = df[df.pred4.notna()].copy()
df["pred_bin"] = (df.pred4 != "safe").astype(int)
y, p4 = df.label_bin, df.pred_bin
print(f"samples scored: {len(df)}   failed API calls (skipped): {n_err}")

# ---- binary (bug = positive) ----
pr, rc, f1, _ = precision_recall_fscore_support(y, p4, average="binary", zero_division=0)
tn, fp, fn, tp = confusion_matrix(y, p4, labels=[0, 1]).ravel()
binm = dict(accuracy=accuracy_score(y, p4), precision=pr, recall=rc, f1=f1, mcc=matthews_corrcoef(y, p4),
            false_positive_rate=fp / max(fp + tn, 1), TP=int(tp), FP=int(fp), TN=int(tn), FN=int(fn))
print("\nBINARY (bug vs safe):"); [print(f"  {k}: {v:.3f}" if isinstance(v, float) else f"  {k}: {v}") for k, v in binm.items()]

# ---- 4-class ----
labs = [c for c in CLASSES if c in set(df.label4) | set(df.pred4)]
print("\n4-CLASS:\n", classification_report(df.label4, df.pred4, labels=labs, zero_division=0))
mf1 = precision_recall_fscore_support(df.label4, df.pred4, labels=labs, average="macro", zero_division=0)[2]
print(f"macro-F1: {mf1:.3f}   4-class accuracy: {accuracy_score(df.label4, df.pred4):.3f}")

# ---- graphs ----
def cm_plot(yt, yp, labels, title, fn, norm=False):
    cm = confusion_matrix(yt, yp, labels=labels).astype(float)
    if norm: cm = cm / np.maximum(cm.sum(1, keepdims=True), 1)
    fig, ax = plt.subplots(figsize=(6.5, 5.5)); im = ax.imshow(cm, cmap="Blues"); plt.colorbar(im)
    ax.set_xticks(range(len(labels))); ax.set_xticklabels(labels, rotation=30, ha="right")
    ax.set_yticks(range(len(labels))); ax.set_yticklabels(labels)
    ax.set_xlabel("Predicted"); ax.set_ylabel("Actual"); ax.set_title(title)
    for i in range(len(labels)):
        for j in range(len(labels)):
            ax.text(j, i, f"{cm[i, j]:.2f}" if norm else int(cm[i, j]), ha="center", va="center",
                    color="white" if cm[i, j] > cm.max() / 2 else "black")
    plt.tight_layout(); plt.savefig(fn, dpi=200); plt.close()

cm_plot(df.label4, df.pred4, labs, "4-class confusion matrix", f"graphs/{a.name}_cm4_counts.png")
cm_plot(df.label4, df.pred4, labs, "4-class confusion matrix (row-normalised)", f"graphs/{a.name}_cm4_norm.png", True)
cm_plot(y, p4, [0, 1], "Binary confusion matrix (0=safe, 1=bug)", f"graphs/{a.name}_cm_binary.png")

pc = precision_recall_fscore_support(df.label4, df.pred4, labels=labs, zero_division=0)
x = np.arange(len(labs)); w = 0.27
fig, ax = plt.subplots(figsize=(8, 5))
for k, (nm, v) in enumerate(zip(["Precision", "Recall", "F1"], pc[:3])): ax.bar(x + (k - 1) * w, v, w, label=nm)
ax.set_xticks(x); ax.set_xticklabels(labs, rotation=15); ax.set_ylim(0, 1.05); ax.legend(); ax.set_title("Per-class metrics")
plt.tight_layout(); plt.savefig(f"graphs/{a.name}_per_class.png", dpi=200); plt.close()

grp = df.assign(correct=(df.label_bin == df.pred_bin)).groupby("group").correct.agg(["mean", "count"]).sort_values("mean")
fig, ax = plt.subplots(figsize=(8, max(3, 0.35 * len(grp)))); ax.barh(grp.index, grp["mean"])
ax.set_xlim(0, 1.05); ax.set_xlabel("Binary accuracy"); ax.set_title("Accuracy by template / CWE group")
plt.tight_layout(); plt.savefig(f"graphs/{a.name}_by_group.png", dpi=200); plt.close()

# ---- tables ----
pd.DataFrame([binm]).to_csv(f"results/{a.name}_binary_metrics.csv", index=False)
pd.DataFrame(classification_report(df.label4, df.pred4, labels=labs, zero_division=0, output_dict=True)).T.to_csv(f"results/{a.name}_4class_report.csv")
grp.to_csv(f"results/{a.name}_by_group.csv")
df.drop(columns=["code"]).to_csv(f"results/{a.name}_predictions.csv", index=False)
df[df.label_bin != df.pred_bin].drop(columns=["code"]).to_csv(f"results/{a.name}_errors.csv", index=False)
print(f"\nSaved graphs/{a.name}_*.png and results/{a.name}_*.csv")
