import time
import requests
import pandas as pd
import streamlit as st

API = "http://127.0.0.1:5000/lb"

st.set_page_config(page_title="Load Balancer Dashboard", layout="wide")
st.title("Load Balancer Dashboard")

with st.sidebar:
    refresh = st.slider("Refresh every (seconds)", 1, 5, 2)
    if st.button("Reset statistics"):
        try:
            requests.get(f"{API}/reset", timeout=2)
        except requests.exceptions.RequestException:
            pass

placeholder = st.empty()

while True:
    try:
        data = requests.get(f"{API}/metrics", timeout=2).json()
    except Exception:
        placeholder.error("Cannot reach the load balancer on port 5000. Is it running?")
        time.sleep(refresh)
        continue

    df = pd.DataFrame(data["servers"])
    df["status"] = df["healthy"].map({True: "UP", False: "DOWN"})

    with placeholder.container():
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Algorithm", data["algorithm"])
        c2.metric("Total requests", int(df["requests"].sum()))
        c3.metric("Servers up", f"{int(df['healthy'].sum())} / {len(df)}")
        c4.metric("Errors / failovers", int(df["errors"].sum()))

        st.subheader("Server status")
        st.dataframe(
            df[["port", "status", "active", "requests", "errors", "avg_ms"]],
            use_container_width=True, hide_index=True,
        )

        left, right = st.columns(2)
        with left:
            st.subheader("Requests per server")
            st.bar_chart(df.set_index("port")["requests"])
        with right:
            st.subheader("Average response time (ms)")
            st.bar_chart(df.set_index("port")["avg_ms"])

        hist = pd.DataFrame(data["history"])
        if not hist.empty:
            st.subheader("Response time of last 200 requests (ms)")
            st.line_chart(hist["ms"])

    time.sleep(refresh)