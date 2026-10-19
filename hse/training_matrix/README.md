# Training Matrix (TRN-700 Rev 1)

Phase 1 of the Training Matrix module: the TRN-701 Employee Training Matrix, built from
TRN-700 Rev 1 Appendix A.

## What it does

- **Training Requirement**: one record per course (TRN-701 Part 1 row). Course ID is the
  controlled document number (e.g. SAF-0012). Holds avenue, delivery, verification, first-due
  rule, refresher, controlled document / revision / section, and R / C codes per Training Role.
- **Training Role**: Technician, Logistics, Customer Service, Manager. Each maps to one or more
  Designations or Departments.
- **Employee Training Matrix**: one per employee (TRN-701 Part 2). Created and updated
  automatically when an Employee is created or their designation, department, hire date or
  status changes. A daily job recalculates Due / Overdue / expiry.
- **Reports**: *Training Requirements Matrix* (Part 1) and *Training Matrix* (Part 2 grid).
- **Training Metric Snapshot**: monthly figures by department and avenue, written on the 1st,
  for trend charts in Frappe Insights.
- **Quality Metrics**: training compliance, overdue, high-hazard overdue and new-hire on-time
  metrics for Quality Goals / Quality Reviews, plus a "Training and Competency" starter goal.

## Status rules

| Status | Part 2 code | Meaning |
|---|---|---|
| Completed | C mm/dd/yy | Completed and current: Qualified |
| Due | D | Due (or refresher due) within 30 days |
| In Progress | IP | Started or awaiting verification: Not Qualified |
| Overdue | OD | Past due, or refresher / certificate lapsed: Not Qualified |
| Confirm Applicability | ? | Conditional (C) course the Manager has not confirmed |
| Not Applicable | — | Not required for this employee |

% Complete = completed required courses ÷ total required courses (Appendix A).

## Setup after deploying

1. Give the Training Coordinator the **Training Coordinator** role (created on migrate).
2. Training Requirement list → **Training Matrix → Load TRN-700 Appendix A**. This creates the
   four Training Roles and the HR, Safety and QMS courses. Technical courses are left for
   Managers to define (the Appendix A rows are illustrative).
3. Open each **Training Role** and add the Designations or Departments it covers. Roles named
   like an existing Designation or Department are mapped automatically.
4. Rename **SAF-TBD-ORIENT** (Safety Orientation) and **SAF-TBD-70E** (NFPA 70E) to their SAF
   numbers, and fill in the delivery and verification fields marked TBD.
5. **Re-sync All Employees** (Training Requirement or Training Role list).
6. Load existing training history: Data Import → Employee Training Matrix → Update Existing
   Records, setting *Completed On* (and *Certificate Expires On* for certifications) on the
   Training rows. From Phase 2, training records fill these in.
7. Managers confirm conditional (C) courses: set *Applicability* on rows showing
   Confirm Applicability.

Courses due "upon assignment" have 0 days allowed, as in the SOP, so they show as Due on the
day they are assigned and Overdue the day after. Raise *Days Allowed* on a course for a grace
period.
