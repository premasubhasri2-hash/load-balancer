import sys
import time
import threading
import hashlib
import requests
from flask import Flask, Response, request, jsonify

SERVERS = [
    {"url": "http://127.0.0.1:5001", "weight": 3},
    {"url": "http://127.0.0.1:5002", "weight": 2},
    {"url": "http://127.0.0.1:5003", "weight": 1},
]

ALGORITHM = sys.argv[1] if len(sys.argv) > 1 else "round_robin"
HEALTH_INTERVAL = 2  # seconds

app = Flask(__name__)
lock = threading.Lock()

healthy = {s["url"]: True for s in SERVERS}
active = {s["url"]: 0 for s in SERVERS}
counter = {"rr": 0, "wrr": 0}
stats = {s["url"]: {"requests": 0, "errors": 0, "total_time": 0.0} for s in SERVERS}
history = []  # last 200 requests: time, server, response time in ms


def health_checker():
    """Background thread: pings every server and updates its status."""
    while True:
        for s in SERVERS:
            url = s["url"]
            try:
                ok = requests.get(f"{url}/health", timeout=1).status_code == 200
            except requests.exceptions.RequestException:
                ok = False
            with lock:
                if healthy[url] != ok:
                    print(f"[HEALTH] {url} is now {'UP' if ok else 'DOWN'}")
                healthy[url] = ok
        time.sleep(HEALTH_INTERVAL)


def pick_server(client_ip, exclude=()):
    with lock:
        alive = [s for s in SERVERS
                 if healthy[s["url"]] and s["url"] not in exclude]
        if not alive:
            return None

        if ALGORITHM == "round_robin":
            server = alive[counter["rr"] % len(alive)]["url"]
            counter["rr"] += 1
        elif ALGORITHM == "weighted":
            pool = [s["url"] for s in alive for _ in range(s["weight"])]
            server = pool[counter["wrr"] % len(pool)]
            counter["wrr"] += 1
        elif ALGORITHM == "least_conn":
            server = min((s["url"] for s in alive), key=lambda u: active[u])
        elif ALGORITHM == "ip_hash":
            h = int(hashlib.md5(client_ip.encode()).hexdigest(), 16)
            server = alive[h % len(alive)]["url"]
        else:
            raise ValueError("Unknown algorithm")

        active[server] += 1
        return server


@app.route("/lb/metrics")
def metrics():
    with lock:
        servers = []
        for s in SERVERS:
            u = s["url"]
            st = stats[u]
            avg = st["total_time"] / st["requests"] if st["requests"] else 0
            servers.append({
                "port": u.split(":")[-1],
                "healthy": healthy[u],
                "active": active[u],
                "requests": st["requests"],
                "errors": st["errors"],
                "avg_ms": round(avg, 1),
            })
        return jsonify({"algorithm": ALGORITHM,
                        "servers": servers,
                        "history": list(history)})


@app.route("/lb/reset")
def reset():
    with lock:
        for st in stats.values():
            st.update(requests=0, errors=0, total_time=0.0)
        history.clear()
    return "reset\n"

@app.route("/lb/algorithm/<name>")
def set_algorithm(name):
    global ALGORITHM
    if name not in ("round_robin", "weighted", "least_conn", "ip_hash"):
        return "unknown algorithm\n", 400
    with lock:
        ALGORITHM = name
        counter["rr"] = 0
        counter["wrr"] = 0
        for st in stats.values():
            st.update(requests=0, errors=0, total_time=0.0)
        history.clear()
    return f"algorithm set to {name}\n"


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def proxy(path):
    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    tried = []
    while True:
        server = pick_server(client_ip, exclude=tried)
        if server is None:
            return Response("No healthy servers available\n", status=503)
        start = time.time()
        try:
            r = requests.get(f"{server}/{path}", timeout=5)
            elapsed = (time.time() - start) * 1000
            with lock:
                stats[server]["requests"] += 1
                stats[server]["total_time"] += elapsed
                history.append({"server": server.split(":")[-1],
                                "ms": round(elapsed, 1)})
                if len(history) > 200:
                    history.pop(0)
            print(f"[{ALGORITHM}] {client_ip} -> {server}")
            return Response(r.content, status=r.status_code)
        except requests.exceptions.RequestException:
            with lock:
                healthy[server] = False
                stats[server]["errors"] += 1
            print(f"[FAILOVER] {server} failed, retrying another server")
            tried.append(server)
        finally:
            with lock:
                active[server] -= 1


if __name__ == "__main__":
    print(f"Load balancer running with algorithm: {ALGORITHM}")
    threading.Thread(target=health_checker, daemon=True).start()
    app.run(port=5000, threaded=True)