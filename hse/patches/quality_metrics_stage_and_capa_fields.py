from hse.quality_metrics.install import make_custom_fields


def execute():
	"""Install the QC Stage objective field and the Rework/NCR/CAPA metric options.
	Code-only releases can skip migrate on Frappe Cloud; a patch makes sure this one runs it."""
	make_custom_fields()
