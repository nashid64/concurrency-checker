"""Fine-tune a code model (default: microsoft/codebert-base) to classify Java code as
safe / race_condition / deadlock / concurrency_issue.

Colab example:
    python training/train.py --data data/all_samples.csv --out training/out/concurrency-model
"""
import argparse
import copy
import json
import os
import random

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
from sklearn.metrics import (accuracy_score, classification_report, confusion_matrix,
                             matthews_corrcoef, precision_recall_fscore_support)
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader
from transformers import AutoModelForSequenceClassification, AutoTokenizer, get_linear_schedule_with_warmup

LABELS = ["safe", "race_condition", "deadlock", "concurrency_issue"]
L2I = {l: i for i, l in enumerate(LABELS)}


def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def make_splits(df, mode, seed):
    """random   : 80/10/10 stratified split (easy, optimistic)
       template : whole code templates are held out for testing (harder, shows generalisation)"""
    if mode == "random":
        train_val, test = train_test_split(df, test_size=0.10, stratify=df.label4, random_state=seed)
    else:
        rng = random.Random(seed)
        held = []
        for label, g in df.groupby("label4"):
            templates = sorted(g["group"].unique())
            n_hold = 2 if label == "safe" else 1
            held += rng.sample(templates, min(n_hold, len(templates) - 1))
        test = df[df["group"].isin(held)]
        train_val = df[~df["group"].isin(held)]
        print("held-out templates (test):", sorted(held))
    train, val = train_test_split(train_val, test_size=0.10, stratify=train_val.label4, random_state=seed)
    return train.reset_index(drop=True), val.reset_index(drop=True), test.reset_index(drop=True)


def make_loader(df, tok, max_len, batch, shuffle, with_labels=True):
    codes = df.code.tolist()
    labels = df.label4.map(L2I).tolist() if with_labels else [0] * len(df)

    def collate(idx):
        enc = tok([codes[i] for i in idx], truncation=True, max_length=max_len, padding=True, return_tensors="pt")
        enc["labels"] = torch.tensor([labels[i] for i in idx])
        return enc

    return DataLoader(list(range(len(df))), batch_size=batch, shuffle=shuffle, collate_fn=collate)


@torch.no_grad()
def predict(model, loader, device):
    model.eval()
    preds, probs = [], []
    for batch in loader:
        batch = {k: v.to(device) for k, v in batch.items() if k != "labels"}
        p = torch.softmax(model(**batch).logits, dim=-1).cpu().numpy()
        probs.append(p)
        preds += p.argmax(1).tolist()
    return np.array(preds), np.concatenate(probs)


def macro_f1(y, p):
    return precision_recall_fscore_support(y, p, labels=list(range(len(LABELS))), average="macro", zero_division=0)[2]


def evaluate(model, tok, df, name, args, device, out_dir):
    loader = make_loader(df, tok, args.max_len, args.batch * 2, False)
    pred, probs = predict(model, loader, device)
    y = df.label4.map(L2I).values
    labs = list(range(len(LABELS)))
    yb, pb = (y != 0).astype(int), (pred != 0).astype(int)
    pr, rc, f1, _ = precision_recall_fscore_support(yb, pb, average="binary", zero_division=0)
    tn, fp, fn, tp = confusion_matrix(yb, pb, labels=[0, 1]).ravel()
    res = {
        "n": int(len(df)),
        "accuracy_4class": float(accuracy_score(y, pred)),
        "macro_f1_4class": float(macro_f1(y, pred)),
        "binary": {"precision": float(pr), "recall": float(rc), "f1": float(f1), "mcc": float(matthews_corrcoef(yb, pb)),
                   "false_positive_rate": float(fp / max(fp + tn, 1)), "TP": int(tp), "FP": int(fp), "TN": int(tn), "FN": int(fn)},
        "report": classification_report(y, pred, labels=labs, target_names=LABELS, zero_division=0, output_dict=True),
    }
    print(f"\n===== {name} (n={len(df)}) =====")
    print(f"4-class accuracy {res['accuracy_4class']:.3f} | macro-F1 {res['macro_f1_4class']:.3f}")
    print(f"binary  P {pr:.3f}  R {rc:.3f}  F1 {f1:.3f}  FPR {res['binary']['false_positive_rate']:.3f}")
    print(classification_report(y, pred, labels=labs, target_names=LABELS, zero_division=0))
    cm = confusion_matrix(y, pred, labels=labs)
    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    im = ax.imshow(cm, cmap="Blues")
    plt.colorbar(im)
    ax.set_xticks(labs); ax.set_xticklabels(LABELS, rotation=30, ha="right")
    ax.set_yticks(labs); ax.set_yticklabels(LABELS)
    ax.set_xlabel("Predicted"); ax.set_ylabel("Actual"); ax.set_title(f"Confusion matrix - {name}")
    for i in labs:
        for j in labs:
            ax.text(j, i, int(cm[i, j]), ha="center", va="center", color="white" if cm[i, j] > cm.max() / 2 else "black")
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, f"confusion_{name}.png"), dpi=200)
    plt.close()
    d = df.drop(columns=["code"]).copy()
    d["pred"] = [LABELS[i] for i in pred]
    d["confidence"] = probs.max(1)
    d.to_csv(os.path.join(out_dir, f"predictions_{name}.csv"), index=False)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/all_samples.csv")
    ap.add_argument("--extra-test", nargs="*", default=["data/test_juliet_38.csv"],
                    help="extra CSVs evaluated after training (default: the 38 Juliet samples)")
    ap.add_argument("--model", default="microsoft/codebert-base", help="HF model name or local folder")
    ap.add_argument("--out", default="training/out/concurrency-model")
    ap.add_argument("--split", choices=["random", "template"], default="random")
    ap.add_argument("--epochs", type=int, default=4)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--max-len", type=int, default=512)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--eval-only", action="store_true", help="skip training, load --out and evaluate")
    args = ap.parse_args()

    set_seed(args.seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print("device:", device, "(training on CPU is very slow - use a GPU runtime in Colab)" if device == "cpu" else "")
    os.makedirs(args.out, exist_ok=True)
    report_dir = os.path.join(os.path.dirname(args.out.rstrip("/\\")) or ".", "reports")
    os.makedirs(report_dir, exist_ok=True)

    df = pd.read_csv(args.data)
    df = df[df.source == "synthetic"] if "source" in df.columns else df  # Juliet stays an external test set
    train, val, test = make_splits(df, args.split, args.seed)
    print(f"train {len(train)} | val {len(val)} | test {len(test)}")

    tok = AutoTokenizer.from_pretrained(args.out if args.eval_only else args.model)
    model = AutoModelForSequenceClassification.from_pretrained(
        args.out if args.eval_only else args.model,
        num_labels=len(LABELS), id2label=dict(enumerate(LABELS)), label2id=L2I,
    ).to(device)

    log = []
    if not args.eval_only:
        tl = make_loader(train, tok, args.max_len, args.batch, True)
        vl = make_loader(val, tok, args.max_len, args.batch * 2, False)
        opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
        total = len(tl) * args.epochs
        sched = get_linear_schedule_with_warmup(opt, int(0.1 * total), total)
        use_amp = device == "cuda"
        try:
            scaler = torch.amp.GradScaler("cuda", enabled=use_amp)
        except (TypeError, AttributeError):
            scaler = torch.cuda.amp.GradScaler(enabled=use_amp)
        best_f1, best_state = -1.0, None
        for epoch in range(1, args.epochs + 1):
            model.train()
            run = 0.0
            for step, batch in enumerate(tl, start=1):
                batch = {k: v.to(device) for k, v in batch.items()}
                with torch.autocast(device_type="cuda", dtype=torch.float16, enabled=use_amp):
                    loss = model(**batch).loss
                opt.zero_grad()
                scaler.scale(loss).backward()
                scaler.unscale_(opt)
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                scaler.step(opt)
                scaler.update()
                sched.step()
                run += loss.item()
                if step % 20 == 0:
                    print(f"epoch {epoch} step {step}/{len(tl)} loss {run / step:.4f}")
            vp, _ = predict(model, vl, device)
            f1 = macro_f1(val.label4.map(L2I).values, vp)
            log.append({"epoch": epoch, "train_loss": run / len(tl), "val_macro_f1": f1})
            print(f"== epoch {epoch}: train_loss {run / len(tl):.4f}  val_macro_F1 {f1:.4f}")
            if f1 > best_f1:
                best_f1 = f1
                best_state = copy.deepcopy({k: v.cpu() for k, v in model.state_dict().items()})
        model.load_state_dict(best_state)
        model.save_pretrained(args.out)
        tok.save_pretrained(args.out)
        pd.DataFrame(log).to_csv(os.path.join(report_dir, "training_log.csv"), index=False)
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.plot([r["epoch"] for r in log], [r["train_loss"] for r in log], marker="o", label="train loss")
        ax.plot([r["epoch"] for r in log], [r["val_macro_f1"] for r in log], marker="o", label="val macro-F1")
        ax.set_xlabel("epoch"); ax.legend(); ax.set_title("Training curve")
        plt.tight_layout(); plt.savefig(os.path.join(report_dir, "training_curve.png"), dpi=200); plt.close()
        print("model saved to", args.out)

    results = {"split_mode": args.split, "base_model": args.model, "val_best_macro_f1": max([r["val_macro_f1"] for r in log], default=None)}
    results["test"] = evaluate(model, tok, test, f"test_{args.split}", args, device, report_dir)
    for path in args.extra_test:
        if os.path.exists(path):
            ex = pd.read_csv(path)
            results[os.path.basename(path)] = evaluate(model, tok, ex, os.path.splitext(os.path.basename(path))[0], args, device, report_dir)
    with open(os.path.join(report_dir, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("\nreports saved to", report_dir)


if __name__ == "__main__":
    main()
