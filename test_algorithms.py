import sys
import random
import collections
import requests
from concurrent.futures import ThreadPoolExecutor

N = int(sys.argv[1]) if len(sys.argv) > 1 else 60

def hit(_):
    fake_ip = f"10.0.{random.randint(0,255)}.{random.randint(0,255)}"
    try:
        r = requests.get("http://127.0.0.1:5000",
                         headers={"X-Forwarded-For": fake_ip}, timeout=10)
        return r.text.strip().split()[-1]
    except Exception:
        return "error"

with ThreadPoolExecutor(max_workers=10) as ex:
    results = list(ex.map(hit, range(N)))

print(f"\nResults for {N} requests:")
for port, count in sorted(collections.Counter(results).items()):
    print(f"  port {port}: {count}")