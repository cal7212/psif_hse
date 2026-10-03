# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Add sample templates for the remaining Light Assembly and Repair stages and refresh
sample templates nobody has used or edited."""

from hse.shop_qc.install import create_sample_templates


def execute():
	create_sample_templates(update_unused=True)
