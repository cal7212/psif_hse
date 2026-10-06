# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cstr, flt


def normalise_fitting(value) -> str:
	return cstr(value).strip().upper().replace(" ", "")


class HoseCrimpSpec(Document):
	def validate(self):
		from hse.shop_qc.doctype.qc_unit.qc_unit import normalise_dash

		self.dash_size = normalise_dash(self.dash_size)[0]
		self.fitting_part_number = normalise_fitting(self.fitting_part_number)
		if flt(self.crimp_diameter) <= 0:
			frappe.throw(_("Crimp Diameter must be greater than zero."))
		if flt(self.crimp_tolerance) < 0:
			frappe.throw(_("Crimp Tolerance must be positive."))
		self.title = f"{self.hose_type} {self.dash_size} {self.fitting_part_number}"
		dupe = frappe.db.get_value(
			"Hose Crimp Spec",
			{
				"hose_type": self.hose_type,
				"dash_size": self.dash_size,
				"fitting_part_number": self.fitting_part_number,
				"name": ("!=", self.name),
			},
		)
		if dupe:
			frappe.throw(
				_("{0} already has a crimp spec for this hose type, dash size and fitting.").format(dupe),
				frappe.DuplicateEntryError,
			)


def find_crimp_spec(hose_type, dash_size, fitting) -> frappe._dict | None:
	"""Active chart row for this hose type, dash size and fitting part number."""
	from hse.shop_qc.doctype.qc_unit.qc_unit import normalise_dash

	if not (hose_type and dash_size and fitting):
		return None
	rows = frappe.get_all(
		"Hose Crimp Spec",
		filters={
			"hose_type": hose_type,
			"dash_size": normalise_dash(dash_size)[0],
			"fitting_part_number": normalise_fitting(fitting),
			"disabled": 0,
		},
		fields=["name", "crimp_diameter", "crimp_tolerance", "die_size", "source", "revision"],
		limit=1,
	)
	return rows[0] if rows else None


@frappe.whitelist()
def get_crimp_spec(hose_type: str, dash_size: str, fitting: str) -> dict | None:
	frappe.has_permission("Hose Crimp Spec", "read", throw=True)
	return find_crimp_spec(hose_type, dash_size, fitting)
