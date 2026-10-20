app_name = "hse"
app_title = "HSE"
app_publisher = "Calvin Johnston"
app_description = "App to manage the OSH program"
app_email = "cjohnston@psifla.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "hse",
# 		"logo": "/assets/hse/logo.png",
# 		"title": "HSE",
# 		"route": "/hse",
# 		"has_permission": "hse.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/hse/css/hse.css"
# app_include_js = "/assets/hse/js/hse.js"

# include js, css files in header of web template
# web_include_css = "/assets/hse/css/hse.css"
# web_include_js = "/assets/hse/js/hse.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "hse/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "hse/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
jinja = {
	"methods": [
		"hse.shop_qc.utils.get_qc_certificate_data",
		"hse.shop_qc.utils.qc_photo_appendix",
		"hse.hse.sds_label.get_ghs_label_data",
	],
}
# jinja = {
# 	"methods": "hse.utils.jinja_methods",
# 	"filters": "hse.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "hse.install.before_install"
# after_install = "hse.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "hse.uninstall.before_uninstall"
# after_uninstall = "hse.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "hse.utils.before_app_install"
# after_app_install = "hse.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "hse.utils.before_app_uninstall"
# after_app_uninstall = "hse.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "hse.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"hse.tasks.all"
# 	],
# 	"daily": [
# 		"hse.tasks.daily"
# 	],
# 	"hourly": [
# 		"hse.tasks.hourly"
# 	],
# 	"weekly": [
# 		"hse.tasks.weekly"
# 	],
# 	"monthly": [
# 		"hse.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "hse.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "hse.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "hse.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "hse.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["hse.utils.before_request"]
# after_request = ["hse.utils.after_request"]

# Job Events
# ----------
# before_job = ["hse.utils.before_job"]
# after_job = ["hse.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"hse.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
export_python_type_annotations = True

# Require all whitelisted methods to have type annotations
require_type_annotated_api_methods = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []
# ---------------------------------------------------------------------------
# Asset Inspection module - MERGE these into hse/hooks.py (do not replace it).
# If a key already exists in your hooks.py, add these entries to it.
# ---------------------------------------------------------------------------

# Requires ERPNext (Asset, Asset Maintenance, Non Conformance)
required_apps = ["erpnext", "hrms"]  # merge if you already list required apps

# Form scripts for standard ERPNext DocTypes
doctype_js = {
	"Asset": "public/js/asset.js",
	"Asset Maintenance Log": "public/js/asset_maintenance_log.js",
	"Non Conformance": [
		"public/js/non_conformance.js",
		"public/js/non_conformance_qc.js",
		"public/js/non_conformance_capa.js",
		"public/js/training_retraining.js",  # Training Matrix: "Retraining Required" (TRN-700 §4.10)
	],
	"Injury_Illness Report": "public/js/training_retraining.js",
	"Quality Review": "public/js/quality_review.js",
	"Quality Goal": "public/js/quality_goal.js",
	"QC Inspection": "public/js/inspection_instruments.js",
	"Asset Inspection": "public/js/inspection_instruments.js",
}

doctype_list_js = {
	"Quality Goal": "public/js/quality_goal_list.js",
}

doc_events = {
	"Non Conformance": {
		"validate": [
			"hse.quality_metrics.ncr.validate",  # QM-104 NCR fields and closure rules; runs first
			"hse.quality_metrics.capa.validate",  # QM-128 CAPA numbering, due dates and closure
			"hse.asset_inspection.events.validate",
			"hse.housekeeping_inspection.events.validate",
			"hse.shop_qc.events.validate",
			"hse.quality_metrics.events.non_conformance_validate",
		],
		"on_update": [
			"hse.asset_inspection.events.on_update",
			"hse.housekeeping_inspection.events.on_update",
			"hse.shop_qc.events.on_update",
		],
	},
	"Quality Goal": {
		"validate": "hse.quality_metrics.events.quality_goal_validate",
	},
	"Quality Review": {
		"validate": "hse.quality_metrics.events.quality_review_validate",
		"on_update": "hse.quality_metrics.events.quality_review_on_update",
	},
	# Training Matrix: keep each employee's TRN-701 matrix in step with HR
	"Employee": {
		"on_update": "hse.training_matrix.events.employee_on_update",
	},
	# Training Matrix: Employee Groups mapped to a Training Role assign its training
	"Employee Group": {
		"on_update": "hse.training_matrix.events.employee_group_on_update",
		"on_trash": "hse.training_matrix.events.employee_group_on_trash",
	},
	# Training Matrix: Frappe Learning completions, quiz scores and certificates (only fire when lms is installed)
	"LMS Enrollment": {
		"on_update": "hse.training_matrix.lms.enrollment_on_update",
	},
	"LMS Quiz Submission": {
		"on_update": "hse.training_matrix.lms.quiz_submission_on_update",
	},
	"LMS Certificate": {
		"on_update": "hse.training_matrix.lms.certificate_on_update",
	},
}

# Housekeeping Inspection: daily Due/Overdue refresh and inspector ToDos
# Training Matrix: daily status refresh; monthly metric snapshot on the 1st
scheduler_events = {
	"daily": [
		"hse.housekeeping_inspection.tasks.update_schedules",
		"hse.training_matrix.tasks.refresh_all_matrices",
		"hse.training_matrix.trainers.refresh_register",
		"hse.training_matrix.lms.reopen_due_refreshers",
		"hse.training_matrix.training_requests.remind_overdue_certificates",
	],
	"cron": {
		"0 2 1 * *": [
			"hse.training_matrix.tasks.write_monthly_snapshot",
		],
		# Training Matrix: every Monday; sends only on the first Monday of the month (TRN-700 §4.9)
		"0 7 * * 1": [
			"hse.training_matrix.notifications.monthly_status_email",
		],
	},
}

# Training Matrix: employees see only their own matrix
permission_query_conditions = {
	"Employee Training Matrix": "hse.training_matrix.permissions.matrix_query_conditions",
	"Training Record": "hse.training_matrix.permissions.record_query_conditions",
	"Competency Evaluation": "hse.training_matrix.permissions.evaluation_query_conditions",
	"Skill Authorization": "hse.training_matrix.permissions.authorization_query_conditions",
	"Retraining Assignment": "hse.training_matrix.permissions.assignment_query_conditions",
	"Training Request": "hse.training_matrix.permissions.request_query_conditions",
}
has_permission = {
	"Employee Training Matrix": "hse.training_matrix.permissions.matrix_has_permission",
	"Training Record": "hse.training_matrix.permissions.record_has_permission",
	"Competency Evaluation": "hse.training_matrix.permissions.evaluation_has_permission",
	"Skill Authorization": "hse.training_matrix.permissions.authorization_has_permission",
	"Retraining Assignment": "hse.training_matrix.permissions.assignment_has_permission",
	"Training Request": "hse.training_matrix.permissions.request_has_permission",
}

# Adds "Inspections" to the Connections tab on Asset Maintenance, Asset and Asset Maintenance Log
override_doctype_dashboards = {
	"Asset Maintenance": "hse.asset_inspection.dashboards.asset_maintenance",
	"Asset": "hse.asset_inspection.dashboards.asset",
	"Asset Maintenance Log": "hse.asset_inspection.dashboards.asset_maintenance_log",
	"Location": "hse.housekeeping_inspection.dashboards.location",
	"Employee": "hse.training_matrix.dashboards.employee",
}

# Custom fields on Asset / Asset Maintenance Task / Asset Maintenance Log /
# Non Conformance are created (idempotently) on install and every migrate.
#
# If hse/hooks.py has NO after_install / after_migrate yet, use:
after_install = [
	"hse.asset_inspection.install.after_install",
	"hse.housekeeping_inspection.install.after_install",
	"hse.hse.sds_setup.after_install",
	"hse.shop_qc.install.after_install",
	"hse.quality_metrics.install.after_install",
	"hse.training_matrix.install.after_install",
]
after_migrate = [
	"hse.module_setup.ensure_module_defs",  # must run first
	"hse.asset_inspection.install.after_migrate",
	"hse.housekeeping_inspection.install.after_migrate",
	"hse.hse.sds_setup.after_migrate",
	"hse.shop_qc.install.after_migrate",
	"hse.quality_metrics.install.after_migrate",
	"hse.training_matrix.install.after_migrate",
]
#
# If you ALREADY have them, either convert to a list (Frappe v16 accepts lists):
#   after_migrate = ["hse.setup.your_existing_hook", "hse.asset_inspection.install.after_migrate"]
# or call this from inside your existing function:
#   from hse.asset_inspection.install import make_custom_fields
#   make_custom_fields()
