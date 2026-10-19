# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt


def employee(data):
	"""Adds the training matrix to the Employee form's Connections tab."""
	data = data or {}
	data.setdefault("fieldname", "employee")
	data.setdefault("transactions", []).append({"label": "Training", "items": ["Employee Training Matrix"]})
	return data
