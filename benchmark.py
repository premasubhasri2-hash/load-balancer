import sys
import csv
import time
import random
import collections
import requests
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from concurrent.futures import ThreadPoolExecutor

BASE = "http://127.0.0.1:5000"
ALGOS = ["round_robin", "weighted", "least_conn", "ip_hash"]
PORTS = ["5001", "5002", "5003"]
N = 300
WORKERS = 20
label = sys.argv[1] if len(sys.argv) > 1 else "equal"


def hit(_):
    ip = f"10.0.{random.randint(0, 255)}.{random.randint(0, 255)}"
    start = time.time()
    try:
        r = requests.get(BASE, headers={"X-Forwarded-For": ip}, timeout=15)
        return r.text.strip().split()[-1], (time.time() - start) * 1000
    except Exception:
        return "error", None


rows = []
for algo in ALGOS:
    requests.get(f"{BASE}/lb/algorithm/{algo}")
    start = time.time()
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        out = list(ex.map(hit, range(N)))
    total = time.time() - start

    times = sorted(ms for _, ms in out if ms is not None)
    counts = collections.Counter(p for p, _ in out)
    rows.append({
        "algorithm": algo,
        "throughput_rps": round(N / total, 1),
        "avg_ms": round(sum(times) / len(times), 1),
        "p95_ms": round(times[int(0.95 * len(times)) - 1], 1),
        "5001": counts["5001"],
        "5002": counts["5002"],
        "5003": counts["5003"],
        "errors": counts["error"],
    })
    print(f"done: {algo}")

# Table
print(f"\nScenario: {label}  ({N} requests, {WORKERS} concurrent)")
print(f"{'algorithm':<13}{'req/s':>8}{'avg ms':>9}{'p95 ms':>9}"
      f"{'5001':>7}{'5002':>7}{'5003':>7}{'errors':>8}")
for r in rows:
    print(f"{r['algorithm']:<13}{r['throughput_rps']:>8}{r['avg_ms']:>9}{r['p95_ms']:>9}"
          f"{r['5001']:>7}{r['5002']:>7}{r['5003']:>7}{r['errors']:>8}")

# CSV
with open(f"results_{label}.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=rows[0].keys())
    w.writeheader()
    w.writerows(rows)

# Charts
x = np.arange(len(ALGOS))
bw = 0.25
fig, ax = plt.subplots(1, 3, figsize=(17, 4.8))

for i, p in enumerate(PORTS):
    ax[0].bar(x + (i - 1) * bw, [r[p] for r in rows], bw, label=f"port {p}")
ax[0].set_title("Requests per server")
ax[0].set_xticks(x)
ax[0].set_xticklabels(ALGOS, rotation=15)
ax[0].legend()

ax[1].bar(x - bw / 2, [r["avg_ms"] for r in rows], bw, label="Average")
ax[1].bar(x + bw / 2, [r["p95_ms"] for r in rows], bw, label="95th percentile")
ax[1].set_title("Response time (ms)")
ax[1].set_xticks(x)
ax[1].set_xticklabels(ALGOS, rotation=15)
ax[1].legend()

ax[2].bar(x, [r["throughput_rps"] for r in rows], 0.5, color="seagreen")
ax[2].set_title("Throughput (requests/second)")
ax[2].set_xticks(x)
ax[2].set_xticklabels(ALGOS, rotation=15)

fig.suptitle(f"Algorithm comparison: {label}")
fig.tight_layout()
out_file = f"screenshots/13_comparison_{label}.png"
fig.savefig(out_file, dpi=150)
print(f"\nChart saved to {out_file}")