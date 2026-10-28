# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""QM-104 NCR and Rework records, with the QM-128 CAPA and QM-134 SCAR tabs.

Replaces ERPNext's Non Conformance. The rules live in hse.quality_metrics (ncr, rework, capa,
scar) and run from doc_events in hooks.py.
"""

from frappe.model.document import Document


class NonconformanceReport(Document):
	pass
