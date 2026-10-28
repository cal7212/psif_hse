// Shop Supplies buttons on the Item, Stock Entry and Stock Reconciliation lists.
["Item", "Stock Entry", "Stock Reconciliation"].forEach((doctype) =>
	window.hse.supplies.extend_list(doctype)
);
