"""
Runs the whole pipeline in order, from raw CSVs to every output.

    python run_pipeline.py

Stage 1  data quality check     -> reports/data_quality_report.md
Stage 2  SQLite + SQL queries   -> data/ecommerce.db, outputs/sql_results/
Stage 3  pandas notebook        -> notebooks/analysis.ipynb (re-executed), images/
Stage 4  Excel summary          -> outputs/ecommerce_summary.xlsx
Stage 5  Tableau exports        -> tableau/*.csv
"""

import subprocess
import sys
from pathlib import Path

import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parent


def run_script(name):
    print(f"\n=== {name}")
    subprocess.run([sys.executable, str(ROOT / "scripts" / name)], check=True)


run_script("01_data_quality_check.py")
run_script("02_build_database.py")

print("\n=== notebooks/analysis.ipynb")
nb_path = ROOT / "notebooks" / "analysis.ipynb"
nb = nbformat.read(nb_path, as_version=4)
NotebookClient(nb, timeout=600, kernel_name="python3",
               resources={"metadata": {"path": str(nb_path.parent)}}).execute()
nbformat.write(nb, nb_path)
print("Notebook executed and saved")

run_script("04_build_excel_summary.py")
run_script("05_export_tableau.py")
print("\nPipeline complete.")
