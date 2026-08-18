"""
pipeline.py

The "ETL" (Extract, Transform, Load) logic for the dashboard.
This file has NO Airflow code in it on purpose — Airflow just calls
these plain Python functions. That separation is a good habit:
your business logic stays testable and runnable on its own,
and Airflow is only the "scheduler / orchestrator" on top.
"""

import sqlite3
import requests
import pandas as pd

DB_PATH = "data/pharma.db"
DRUG_NAME = "remibrutinib"


def get_trials(drug: str = DRUG_NAME) -> pd.DataFrame:
    """Pull clinical trials for the drug from ClinicalTrials.gov (API v2)."""
    url = "https://clinicaltrials.gov/api/v2/studies"
    params = {
        "query.term": drug,
        "pageSize": 100,
    }

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    rows = []
    for study in data.get("studies", []):
        protocol = study.get("protocolSection", {})
        identification = protocol.get("identificationModule", {})
        status_module = protocol.get("statusModule", {})
        design = protocol.get("designModule", {})
        conditions = protocol.get("conditionsModule", {})
        sponsor = protocol.get("sponsorCollaboratorsModule", {})

        rows.append({
            "trial_id": identification.get("nctId"),
            "title": identification.get("briefTitle"),
            "status": status_module.get("overallStatus"),
            "phase": ", ".join(design.get("phases", [])) or "N/A",
            "conditions": ", ".join(conditions.get("conditions", [])) or "N/A",
            "sponsor": sponsor.get("leadSponsor", {}).get("name", "N/A"),
            "start_date": status_module.get("startDateStruct", {}).get("date", "N/A"),
        })

    return pd.DataFrame(rows)


def get_pubmed(drug: str = DRUG_NAME, retmax: int = 25) -> pd.DataFrame:
    """Pull the most recent PubMed publications mentioning the drug."""
    # Step 1: search for matching article IDs
    search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    search_params = {
        "db": "pubmed",
        "term": drug,
        "retmode": "json",
        "retmax": retmax,
        "sort": "date",  #
    }
    search_resp = requests.get(search_url, params=search_params, timeout=30)
    search_resp.raise_for_status()
    ids = search_resp.json()["esearchresult"]["idlist"]

    if not ids:
        return pd.DataFrame(columns=["pubmed_id", "title", "journal", "pub_date"])
    summary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    summary_params = {
        "db": "pubmed",
        "id": ",".join(ids),
        "retmode": "json",
    }
    summary_resp = requests.get(summary_url, params=summary_params, timeout=30)
    summary_resp.raise_for_status()
    result = summary_resp.json()["result"]

    rows = []
    for pmid in ids:
        item = result.get(pmid, {})
        rows.append({
            "pubmed_id": pmid,
            "title": item.get("title", "N/A"),
            "journal": item.get("source", "N/A"),
            "pub_date": item.get("pubdate", "N/A"),
        })

    df = pd.DataFrame(rows)
    df["pub_date_parsed"] = pd.to_datetime(df["pub_date"], errors="coerce")
    df = df.sort_values("pub_date_parsed", ascending=False)
    df = df.drop(columns=["pub_date_parsed"]).reset_index(drop=True)
    return df


def save_data() -> None:
    """Run both extracts and write them to SQLite. This is the function
    both the CLI (`python pipeline.py`) and the Airflow DAG call."""
    trials = get_trials()
    publications = get_pubmed()

    connection = sqlite3.connect(DB_PATH)
    trials.to_sql("clinical_trials", connection, if_exists="replace", index=False)
    publications.to_sql("publications", connection, if_exists="replace", index=False)
    connection.close()

    print(f"Saved {len(trials)} trials and {len(publications)} publications to {DB_PATH}")


if __name__ == "__main__":
    save_data()
