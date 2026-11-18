import sys
import time
import random
from flask import Flask

port = int(sys.argv[1])
extra = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
app = Flask(__name__)

@app.route("/health")
def health():
    return "OK"

@app.route("/")
def home():
    time.sleep(random.uniform(0.05, 0.3) + extra)
    return f"Response from Server on port {port}\n"

app.run(port=port, threaded=True)