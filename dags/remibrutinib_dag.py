from datetime import datetime
import sys
import sqlite3
from airflow.sdk import DAG, task
sys.path.append("/Users/juinnshengna/Desktop/remibrutinib")

from pipeline import get_trials, get_pubmed, DB_PATH


# DAG is basically a workflow that tells Airflow what tasks to run, in what order, and how often
with DAG(
    dag_id="remibrutinib_pipeline",

    description=(
        "Pull remibrutinib clinical trial and "
        "PubMed data into SQLite daily"
    ),

    #Cut off date
    start_date=datetime(2026, 8, 18),

    # Run daily
    schedule="@daily",

    # Prevent Airflow from running all missed historical executions when you first enable the DAG.
    catchup=False,

    # Tags make the DAG easier to find in the Airflow UI.
    tags=[
        "remibrutinib",
        "pharma",
        "clinical-trials",
        "pubmed",
    ],
) as dag:

    # Task 1: Extract clinical trials
    @task
    def extract_trials():
        df = get_trials()
        print(
            f"Fetched {len(df)} clinical trials"
        )

        # Airflow needs XCom data to be JSON serializable.
        # Pandas DataFrame itself cannot be passed directly, so convert it into a list of dictionaries.
        return df.to_dict("records")


    # Task 2: Create publication
    @task
    def extract_publications():

        # Call the PubMed function from pipeline.py.
        df = get_pubmed()

        # Show the number of publications retrieved.
        print(
            f"Fetched {len(df)} publications"
        )

        # Convert DataFrame into JSON-compatible records so Airflow can pass the result to the next task.
        return df.to_dict("records")


    # Save to SQLite
    @task
    def load_to_sqlite(
        trial_records,
        publication_records
    ):

        import pandas as pd
        trials_df = pd.DataFrame(
            trial_records
        )

        publications_df = pd.DataFrame(
            publication_records
        )


        # Connect to your SQLite database.
        connection = sqlite3.connect(
            DB_PATH
        )


        # Save clinical trial data.
        # if_exists="replace" means the existing table is replaced every time the DAG runs.
        trials_df.to_sql(
            "clinical_trials",
            connection,
            if_exists="replace",
            index=False,
        )


        # Save PubMed data.
        publications_df.to_sql(
            "publications",
            connection,
            if_exists="replace",
            index=False,
        )


        # Close the database connection.
        connection.close()


        print(
            "Load complete — dashboard data refreshed."
        )


    # Run Task

    # Task 1
    trials = extract_trials()

    # Task 2
    publications = extract_publications()


    # Task 3 - This task receives the output from BOTH previous tasks.
    load_to_sqlite(
        trials,
        publications
    )