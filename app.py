"""
app.py

The dashboard. Reads whatever is currently in data/pharma.db and displays it.
It doesn't know or care whether that data was put there by `python pipeline.py`
or by an Airflow run — that's the whole point of separating storage from
the pipeline and from the UI.
"""

import sqlite3
import pandas as pd
import plotly.express as px
import streamlit as st

from pipeline import save_data, DB_PATH

st.set_page_config(page_title="Remibrutinib Intelligence", layout="wide")

st.title("💊 Remibrutinib Clinical Intelligence Dashboard")
st.caption("Live view of ClinicalTrials.gov trials and recent PubMed research on remibrutinib.")

# --- Sidebar: manual refresh button ---
with st.sidebar:
    st.header("Data")
    if st.button("🔄 Refresh data now"):
        with st.spinner("Pulling latest data from ClinicalTrials.gov and PubMed..."):
            save_data()
        st.success("Data refreshed!")
        st.rerun()
    st.caption("In production this refresh is what your Airflow DAG does on a schedule.")

# --- Load data ---
try:
    connection = sqlite3.connect(DB_PATH)
    trials = pd.read_sql("SELECT * FROM clinical_trials", connection)
    publications = pd.read_sql("SELECT * FROM publications", connection)
    connection.close()
except Exception:
    st.warning("No data yet. Run `python pipeline.py` once, or click Refresh in the sidebar.")
    st.stop()

# --- Top-line metrics ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Trials", len(trials))
col2.metric("Recruiting Trials", int((trials["status"] == "RECRUITING").sum()))
col3.metric("Publications Found", len(publications))
latest_year = "N/A"
if not publications.empty and publications["pub_date"].notna().any():
    latest_year = publications.sort_values("pub_date", ascending=False)["pub_date"].iloc[0]
col4.metric("Most Recent Publication", latest_year)

st.divider()

# --- Charts ---
chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.subheader("Trials by Status")
    if not trials.empty:
        status_counts = trials["status"].value_counts().reset_index()
        status_counts.columns = ["status", "count"]
        fig = px.bar(status_counts, x="status", y="count", color="status", text="count")
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No trial data yet.")

with chart_col2:
    st.subheader("Trials by Phase")
    if not trials.empty:
        phase_counts = trials["phase"].value_counts().reset_index()
        phase_counts.columns = ["phase", "count"]
        fig = px.pie(phase_counts, names="phase", values="count", hole=0.4)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No trial data yet.")

st.divider()

# --- Trials table ---
st.subheader("All Clinical Trials")
st.dataframe(trials, use_container_width=True, hide_index=True)

st.divider()

# --- Latest publications ---
st.subheader("Latest Research Findings")
if publications.empty:
    st.info("No publications found yet.")
else:
    for _, row in publications.head(10).iterrows():
        st.markdown(
            f"**{row['title']}**  \n"
            f"{row['journal']} — {row['pub_date']}  \n"
            f"[View on PubMed](https://pubmed.ncbi.nlm.nih.gov/{row['pubmed_id']}/)"
        )
        st.markdown("---")
