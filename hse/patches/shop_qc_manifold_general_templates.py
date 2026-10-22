# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Sample templates for the HPU-shop stages on Manifold units and on units whose product
type has no template of its own (Component, Other, Valve Stand). Existing templates are
left alone; Power Units keep their own templates, which outrank a blank product type."""

from hse.shop_qc.install import create_sample_templates


def execute():
	create_sample_templates()
