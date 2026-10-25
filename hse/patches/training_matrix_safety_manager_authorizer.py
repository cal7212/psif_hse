# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Safety Manager role; it also authorizes the Respirator Fit Tester skill."""

from hse.training_matrix.setup.respirator import set_authorizer_roles


def execute():
	set_authorizer_roles()
