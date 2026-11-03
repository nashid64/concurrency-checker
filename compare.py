import pandas as pd, json
rows = []
for ds, pre in [("Juliet-38", "juliet"), ("Synthetic-100", "syn100")]:
    for m in ["model", "llm", "hybrid"]:
        b = pd.read_csv(f"results/{pre}_{m}_binary_metrics.csv").iloc[0]
        lat = [json.loads(l)["response"]["elapsed_ms"] for l in open(f"results/{pre}_{m}.jsonl", encoding="utf-8")
               if json.loads(l)["response"]]
        rows.append(dict(dataset=ds, mode=m, accuracy=b.accuracy, precision=b.precision, recall=b.recall,
                         f1=b.f1, mcc=b.mcc, fpr=b.false_positive_rate, avg_ms=sum(lat)/len(lat)))
t = pd.DataFrame(rows).round(3)
print(t.to_string(index=False)); t.to_csv("results/comparison.csv", index=False)