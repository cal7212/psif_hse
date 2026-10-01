"""Push HPU work orders from a TrulinX export to Frappe.

Run on a machine that can see the TrulinX export (Windows Task Scheduler every 15 min, or cron).
  pip install requests
  set FRAPPE_URL=https://erp.example.com
  set FRAPPE_API_KEY=...      (API key of the "HPU Sync" integration user)
  set FRAPPE_API_SECRET=...
  python trulinx_hpu_sync.py "\\\\server\\exports\\hpu_work_orders.csv"

CSV source: a saved TrulinX MS Query / SQL report filtered to HPU work orders, with columns
named like FIELD_MAP keys in hse/hpu_build/api.py (work_order, model, serial_no, ...).
COLUMN_RENAMES below translates the real TrulinX column headers if they differ.
"""

import csv
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

import requests

BATCH = 200
COLUMN_RENAMES = {
	# "WO_NUM": "work_order",
	# "PART_NO": "model",
	# "CUST_NAME": "customer_name",
	# "SO_NUM": "sales_order",
	# "WO_STAT": "wo_status",
	# "PROM_DATE": "promised_date",
}


def read_rows(path: Path) -> list[dict]:
	with path.open(newline="", encoding="utf-8-sig") as fh:
		rows = []
		for raw in csv.DictReader(fh):
			row = {COLUMN_RENAMES.get(k.strip(), k.strip().lower()): (v or "").strip() for k, v in raw.items() if k}
			if row.get("work_order"):
				rows.append(row)
		return rows


def push(rows: list[dict]) -> dict:
	url = os.environ["FRAPPE_URL"].rstrip("/") + "/api/method/hse.hpu_build.api.upsert_hpu_units"
	headers = {"Authorization": f"token {os.environ['FRAPPE_API_KEY']}:{os.environ['FRAPPE_API_SECRET']}"}
	totals = {"created": [], "updated": [], "unchanged": [], "errors": []}
	for i in range(0, len(rows), BATCH):
		resp = requests.post(url, json={"units": rows[i : i + BATCH]}, headers=headers, timeout=120)
		resp.raise_for_status()
		for k, v in resp.json()["message"].items():
			totals[k].extend(v)
	return totals


def main():
	src = Path(sys.argv[1])
	rows = read_rows(src)
	result = push(rows)
	stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
	print(
		f"{stamp} rows={len(rows)} created={len(result['created'])} updated={len(result['updated'])} "
		f"unchanged={len(result['unchanged'])} errors={len(result['errors'])}"
	)
	for err in result["errors"]:
		print("  ERROR", err)
	archive = src.parent / "processed"
	archive.mkdir(exist_ok=True)
	shutil.copy2(src, archive / f"{src.stem}-{stamp}{src.suffix}")
	sys.exit(1 if result["errors"] else 0)


if __name__ == "__main__":
	main()
