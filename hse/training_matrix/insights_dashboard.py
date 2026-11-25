# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Frappe Insights workbook: course completion in Frappe Learning batches (TRN-700 Rev 1).

Progress for each batch member on each course in the batch, broken down by Training Role,
Department and member, with Batch, Course, Department and Training Role dashboard filters.

- Training Roles come from the Training Role mappings (Designations, Departments and Employee
  Groups), the same rules as `matrix.roles_for_employee`, so the dashboard is current even before
  a matrix re-syncs. Manual roles on a matrix with "Roles from Designation / Department" cleared
  are not shown.
- Two measures sit side by side: LMS completion (100% progress) and Qualified (the Employee
  Training Matrix row). A course finished in Learning is not Qualified until the quizzes pass and
  the TRN-702 record exists, and a refresher clears LMS progress while the earlier
  qualification still holds.

Active only when insights, lms and hrms are installed. The workbook is built in the format
Insights exports (the "wrapped" format) and imported through Insights' own import, which
upgrades it to the installed version. It is created once, under WORKBOOK_TITLE, and never
overwritten, so edits made in Insights are kept. To rebuild it, delete or rename the workbook
and run:

    bench --site <site> execute hse.training_matrix.insights_dashboard.setup
"""

import frappe

WORKBOOK_TITLE = "LMS Batch Training Progress"
DASHBOARD_TITLE = "Batch Course Completion"
DATA_SOURCE = "Site DB"

# Placeholder names inside the file. Insights gives every member a new name on import.
WORKBOOK = "hse-lms-batch-progress"
QUERY_PROGRESS = "hse-q-batch-course-progress"
QUERY_BY_ROLE = "hse-q-batch-progress-by-role"

# ---------------------------------------------------------------- SQL
# One row per employee per enabled Training Role, with how the role was assigned. Mirrors
# matrix.roles_for_employee: Designation, Department and Employee Group mappings.
ROLE_SQL = """
SELECT x.employee AS employee,
       x.training_role AS training_role,
       GROUP_CONCAT(DISTINCT x.via ORDER BY x.via SEPARATOR ', ') AS role_via
FROM (
    SELECT emp.name AS employee, trd.parent AS training_role, 'Designation' AS via
    FROM `tabEmployee` emp
    JOIN `tabTraining Role Designation` trd
      ON trd.designation = emp.designation AND trd.parenttype = 'Training Role'
    UNION ALL
    SELECT emp.name, trdp.parent, 'Department'
    FROM `tabEmployee` emp
    JOIN `tabTraining Role Department` trdp
      ON trdp.department = emp.department AND trdp.parenttype = 'Training Role'
    UNION ALL
    SELECT egt.employee, treg.parent, 'Employee Group'
    FROM `tabEmployee Group Table` egt
    JOIN `tabTraining Role Employee Group` treg
      ON treg.employee_group = egt.parent AND treg.parenttype = 'Training Role'
    WHERE egt.parenttype = 'Employee Group'
) x
JOIN `tabTraining Role` tro ON tro.name = x.training_role AND tro.disabled = 0
GROUP BY x.employee, x.training_role
"""

# Batch members x the batch's courses, with LMS progress, the employee and their matrix row.
BATCH_FROM_SQL = """
FROM `tabLMS Batch Enrollment` be
JOIN `tabLMS Batch` lb ON lb.name = be.batch
JOIN `tabBatch Course` bc ON bc.parent = lb.name AND bc.parenttype = 'LMS Batch'
JOIN `tabLMS Course` c ON c.name = bc.course
LEFT JOIN `tabLMS Enrollment` e ON e.member = be.member AND e.course = bc.course
LEFT JOIN `tabEmployee` emp ON emp.user_id = be.member AND emp.status = 'Active'
"""

MATRIX_JOIN_SQL = """
LEFT JOIN `tabTraining Requirement` tr ON tr.lms_course = bc.course AND tr.disabled = 0
LEFT JOIN `tabEmployee Training Matrix Item` i
  ON i.parent = emp.name
 AND i.parenttype = 'Employee Training Matrix'
 AND i.training_requirement = tr.name
"""

# One row per member per course per batch. Training Roles are joined into one column, so an
# employee with several roles is counted once.
PROGRESS_SQL = f"""
SELECT
    lb.name AS batch,
    lb.title AS batch_title,
    bc.course AS course,
    c.title AS course_title,
    tr.name AS course_id,
    be.member AS member,
    COALESCE(emp.employee_name, be.member_name, be.member) AS member_name,
    emp.name AS employee,
    COALESCE(emp.department, 'No Employee Record') AS department,
    COALESCE(r.training_roles, 'No Training Role') AS training_roles,
    COALESCE(e.progress, 0) AS progress,
    CASE WHEN e.progress >= 100 THEN 100 ELSE 0 END AS completion_pct,
    CASE
        WHEN e.name IS NULL THEN 'Not Enrolled'
        WHEN e.progress >= 100 THEN 'Completed'
        WHEN e.progress > 0 THEN 'In Progress'
        ELSE 'Not Started'
    END AS lms_status,
    COALESCE(i.status, 'Not on Matrix') AS matrix_status,
    COALESCE(i.qualification, 'Not Qualified') AS qualification,
    CASE WHEN i.qualification = 'Qualified' THEN 100 ELSE 0 END AS qualified_pct,
    i.due_date AS due_date
{BATCH_FROM_SQL}
LEFT JOIN (
    SELECT d.employee AS employee,
           GROUP_CONCAT(d.training_role ORDER BY d.training_role SEPARATOR ', ') AS training_roles
    FROM ({ROLE_SQL}) d
    GROUP BY d.employee
) r ON r.employee = emp.name
{MATRIX_JOIN_SQL}
"""

# One row per member per course per batch per Training Role, for the role breakdown.
# role_requirement is the Training Requirement's R / C code for that role.
BY_ROLE_SQL = f"""
SELECT
    lb.title AS batch_title,
    c.title AS course_title,
    be.member AS member,
    COALESCE(emp.employee_name, be.member_name, be.member) AS member_name,
    COALESCE(emp.department, 'No Employee Record') AS department,
    COALESCE(er.training_role, 'No Training Role') AS training_role,
    er.role_via AS role_via,
    COALESCE(trr.requirement_code, 'Not required by role') AS role_requirement,
    COALESCE(e.progress, 0) AS progress,
    CASE WHEN e.progress >= 100 THEN 100 ELSE 0 END AS completion_pct,
    CASE WHEN i.qualification = 'Qualified' THEN 100 ELSE 0 END AS qualified_pct
{BATCH_FROM_SQL}
LEFT JOIN ({ROLE_SQL}) er ON er.employee = emp.name
{MATRIX_JOIN_SQL}
LEFT JOIN `tabTraining Requirement Role` trr
  ON trr.parent = tr.name
 AND trr.parenttype = 'Training Requirement'
 AND trr.training_role = er.training_role
"""


# ---------------------------------------------------------------- setup
def installed() -> bool:
	apps = frappe.get_installed_apps()
	return all(app in apps for app in ("insights", "lms", "hrms"))


def setup() -> str | None:
	"""Import the workbook once. Returns its name, or None when skipped or failed.

	Never raises, so a migrate does not stop here; failures go to the Error Log."""
	if not installed():
		print("Training Matrix: Insights, Learning or HR is not installed; batch dashboard skipped.")
		return None
	existing = frappe.db.get_value("Insights Workbook", {"title": WORKBOOK_TITLE}, "name")
	if existing:
		return existing
	if not frappe.db.exists("Insights Data Source v3", DATA_SOURCE):
		print(f"Training Matrix: Insights has no {DATA_SOURCE!r} data source yet; batch dashboard skipped.")
		return None

	try:
		from insights.insights.doctype.insights_workbook.insights_workbook import import_workbook

		result = import_workbook(workbook())
	except Exception:
		frappe.log_error(title="Training Matrix: Insights batch dashboard")
		print("Training Matrix: the Insights batch dashboard could not be created; see Error Log.")
		return None

	# Insights 3.50 returns {"workbook": name, "names": {...}}; earlier v3 returns the name.
	name = result.get("workbook") if isinstance(result, dict) else result
	print(f"Training Matrix: created Insights workbook {WORKBOOK_TITLE!r} ({name}).")
	return name


# ---------------------------------------------------------------- workbook file
def workbook() -> dict:
	"""The workbook in Insights' export format (version 1.0, "wrapped")."""
	charts = {chart["name"]: chart for chart in _charts()}
	return {
		"version": "1.0",
		"type": "Workbook",
		"name": WORKBOOK,
		"doc": {"name": WORKBOOK, "title": WORKBOOK_TITLE},
		"dependencies": {
			"folders": [],
			"queries": {
				QUERY_PROGRESS: _query(QUERY_PROGRESS, "Batch Course Progress", PROGRESS_SQL, 0),
				QUERY_BY_ROLE: _query(QUERY_BY_ROLE, "Batch Progress by Training Role", BY_ROLE_SQL, 1),
			},
			"charts": charts,
			"dashboards": {"hse-d-batch-completion": _dashboard(charts)},
		},
	}


def _query(name: str, title: str, sql: str, sort_order: int) -> dict:
	return {
		"name": name,
		"title": title,
		"workbook": WORKBOOK,
		"sort_order": sort_order,
		# Live: the SQL runs on the site database, not on a Data Store copy.
		"use_live_connection": 1,
		"is_native_query": 1,
		"is_builder_query": 0,
		"is_script_query": 0,
		"operations": [{"type": "sql", "raw_sql": sql.strip(), "data_source": DATA_SOURCE}],
	}


def _dim(column: str, data_type: str = "String", **extra) -> dict:
	return {"dimension_name": column, "column_name": column, "data_type": data_type, **extra}


def _measure(label: str, column: str, aggregation: str, data_type: str = "Decimal") -> dict:
	return {
		"measure_name": label,
		"column_name": column,
		"data_type": data_type,
		"aggregation": aggregation,
	}


AVG_PROGRESS = _measure("Avg Progress", "progress", "avg")
LMS_COMPLETION = _measure("LMS Completion Rate", "completion_pct", "avg")
QUALIFIED = _measure("Qualified Rate", "qualified_pct", "avg")
ASSIGNMENTS = _measure("Course Assignments", "member", "count", "Integer")
LEARNERS = _measure("Learners", "member", "count_distinct", "Integer")

# Each role is judged on the courses it requires (R) or conditionally requires (C).
ROLE_REQUIRES_COURSE = {
	"logical_operator": "And",
	"filters": [
		{
			"column": {"type": "column", "column_name": "role_requirement"},
			"operator": "in",
			"value": ["R", "C"],
		}
	],
}
NO_FILTERS = {"logical_operator": "And", "filters": []}


def _chart(name, title, query, chart_type, config, filters=None, limit=100) -> dict:
	return {
		"name": name,
		"title": title,
		"workbook": WORKBOOK,
		"query": query,
		"chart_type": chart_type,
		"config": {**config, "filters": filters or NO_FILTERS, "order_by": [], "limit": limit},
	}


def _bar(name, title, query, dimension, filters=None) -> dict:
	series = [{"measure": m} for m in (LMS_COMPLETION, QUALIFIED, AVG_PROGRESS)]
	config = {
		"x_axis": {"dimension": _dim(dimension)},
		"y_axis": {"series": series, "stack": False, "show_data_labels": True, "max": 100},
	}
	return _chart(name, title, query, "Bar", config, filters)


def _donut(name, title, column) -> dict:
	config = {"label_column": _dim(column), "value_column": ASSIGNMENTS, "show_inline_labels": True}
	return _chart(name, title, QUERY_PROGRESS, "Donut", config)


def _table(name, title, query, rows, columns, values, filters=None, limit=100) -> dict:
	config = {
		"rows": rows,
		"columns": columns,
		"values": values,
		"max_column_values": 25,
		"enable_color_scale": True,
	}
	return _chart(name, title, query, "Table", config, filters, limit)


def _charts() -> list[dict]:
	percent = {"decimal": 1, "suffix": "%"}
	summary = {
		"number_columns": [LEARNERS, ASSIGNMENTS, AVG_PROGRESS, LMS_COMPLETION, QUALIFIED],
		"number_column_options": [{}, {}, percent, percent, percent],
		"comparison": False,
		"sparkline": False,
	}
	return [
		_chart("hse-c-summary", "Batch Summary", QUERY_PROGRESS, "Number", summary),
		_donut("hse-c-lms-status", "LMS Status", "lms_status"),
		_donut("hse-c-matrix-status", "Training Matrix Status", "matrix_status"),
		_bar(
			"hse-c-by-role", "Progress by Training Role", QUERY_BY_ROLE, "training_role", ROLE_REQUIRES_COURSE
		),
		_bar("hse-c-by-department", "Progress by Department", QUERY_PROGRESS, "department"),
		_bar("hse-c-by-course", "Progress by Course", QUERY_PROGRESS, "course_title"),
		_bar("hse-c-by-batch", "Progress by Batch", QUERY_PROGRESS, "batch_title"),
		_table(
			"hse-c-role-department",
			"Completion: Department x Training Role",
			QUERY_BY_ROLE,
			[_dim("department")],
			[_dim("training_role")],
			[LMS_COMPLETION],
			ROLE_REQUIRES_COURSE,
		),
		_table(
			"hse-c-member-course",
			"Progress: Member x Course",
			QUERY_PROGRESS,
			[_dim("member_name"), _dim("department")],
			[_dim("course_title")],
			[AVG_PROGRESS],
			limit=1000,
		),
		_table(
			"hse-c-member-detail",
			"Member Detail",
			QUERY_PROGRESS,
			[
				_dim(column)
				for column in (
					"member_name",
					"department",
					"training_roles",
					"batch_title",
					"course_title",
					"lms_status",
					"matrix_status",
				)
			],
			[],
			[AVG_PROGRESS],
			limit=1000,
		),
	]


# ---------------------------------------------------------------- dashboard
# Insights lays out v3.15 dashboards on 20 columns (52 px rows); 3.50 rescales on import.
LAYOUT = [
	# (chart, x, y, w, h)
	("hse-c-summary", 0, 2, 20, 3),
	("hse-c-lms-status", 0, 5, 10, 8),
	("hse-c-matrix-status", 10, 5, 10, 8),
	("hse-c-by-role", 0, 13, 10, 8),
	("hse-c-by-department", 10, 13, 10, 8),
	("hse-c-by-course", 0, 21, 10, 8),
	("hse-c-by-batch", 10, 21, 10, 8),
	("hse-c-role-department", 0, 29, 20, 8),
	("hse-c-member-course", 0, 37, 20, 10),
	("hse-c-member-detail", 0, 47, 20, 12),
]

# (filter, column on Batch Course Progress, column on Batch Progress by Training Role, operator)
FILTERS = [
	("Batch", "batch_title", "batch_title", None),
	("Course", "course_title", "course_title", None),
	("Department", "department", "department", None),
	# Batch Course Progress lists all of an employee's roles in one column, hence "contains".
	("Training Role", "training_roles", "training_role", "contains"),
]

INTRO = (
	"**LMS Completion Rate**: share of course assignments at 100% in Learning. "
	"**Qualified Rate**: share Qualified on the Employee Training Matrix (TRN-702 record or "
	"TRN-704 evaluation). Training Role charts count only courses the role requires (R / C)."
)


def _dashboard(charts: dict) -> dict:
	items = [{"type": "text", "text": INTRO, "layout": _layout("intro", 0, 1, 20, 1)}]
	for index, (label, progress_column, role_column, operator) in enumerate(FILTERS):
		links = {}
		for chart_name, chart in charts.items():
			if chart["query"] == QUERY_BY_ROLE:
				links[chart_name] = f"`{QUERY_BY_ROLE}`.`{role_column}`"
			else:
				links[chart_name] = f"`{QUERY_PROGRESS}`.`{progress_column}`"
		item = {
			"type": "filter",
			"filter_name": label,
			"filter_type": "String",
			"links": links,
			"layout": _layout(f"filter-{index}", index * 5, 0, 5, 1),
		}
		if operator:
			item["default_operator"] = operator
		items.append(item)

	for chart, x, y, w, h in LAYOUT:
		items.append({"type": "chart", "chart": chart, "layout": _layout(chart, x, y, w, h)})

	return {
		"name": "hse-d-batch-completion",
		"title": DASHBOARD_TITLE,
		"workbook": WORKBOOK,
		"items": items,
	}


def _layout(key: str, x: int, y: int, w: int, h: int) -> dict:
	return {"i": key, "x": x, "y": y, "w": w, "h": h, "moved": False}
