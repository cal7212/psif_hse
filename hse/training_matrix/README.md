# Training Matrix (TRN-700 Rev 1)

Phase 1: the TRN-701 Employee Training Matrix, built from TRN-700 Rev 1 Appendix A.
Phase 2: training records, competency evaluations, the Qualified Trainer register and the
Frappe Learning integration.
Phase 2b: skills built from courses, granted by manager authorization and mirrored to the
Frappe HR Employee Skill Map.

## What it does

- **Training Requirement**: one record per course (TRN-701 Part 1 row). Course ID is the
  controlled document number (e.g. SAF-0012). Holds avenue, delivery, verification, first-due
  rule, refresher, controlled document / revision / section, and R / C codes per Training Role.
- **Training Role**: Technician, Logistics, Customer Service, Manager. Each maps to one or more
  Designations, Departments or Employee Groups. Use Employee Groups for work that doesn't follow
  job titles (e.g. a *Respirator Users* role mapped to a *Respirator Users* group): adding someone
  to the group assigns the training, removing them drops it (training history is kept).
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

## Phase 2: records, evaluations and Frappe Learning

- **Training Record (TRN-702)**: submitted records are locked; corrections are cancel and amend.
  One row per attendee with score, result, acknowledgment and certificate. Sources: Classroom,
  OJT, Read & Acknowledge, LMS Course (created automatically) and External Certificate.
- **Acknowledgment**: classroom, OJT and read-and-acknowledge records count only after each
  attendee acknowledges under their own login. Attendees are emailed a link to *My Training*.
- **Competency Evaluation (TRN-704)**: checklist from a *Competency Checklist Template*, overall
  Pass / Fail, basis Training or Prior Experience (evidence required). A failed evaluation is
  assigned to the employee's manager (Reports To) for retraining.
- **Qualified Trainer**: courses each trainer may train and evaluate, who designated them and
  their certification. A trainer must be Qualified in the course first; a course is suspended
  automatically while the certification is expired or the trainer's own qualification lapses.
  Active trainers get the **Qualified Trainer** role, which lets them create records and
  evaluations. High-hazard courses (*Requires Qualified Trainer*) only accept authorized
  trainers and evaluators.
- **Which evidence qualifies**: courses verified by quiz, acknowledgment, completion record or
  certificate are qualified by an acknowledged, passing training record. Courses verified by
  practical demonstration, observation, a TRN-704 checklist, or quiz and MVR review need a
  passing Competency Evaluation; until then the row is In Progress. Hand-entered history is
  kept unless newer evidence replaces it.

### Frappe Learning

- Each Training Requirement has an **LMS Course** field (added on migrate when Frappe Learning
  is installed). Employees who need the course are enrolled automatically.
- Finishing the course (100% progress, and every quiz passed at its pass mark, or 80% for
  quiz-verified courses) creates and submits a TRN-702 record. An LMS Certificate's expiry date
  is copied to the record.
- When a refresher falls due, the course's lesson progress is cleared so the employee retakes
  it. Set quizzes in refresher courses to allow enough attempts (*Max Attempts* 0 = unlimited).
- A **My Training** link is added to the Learning portal sidebar. It shows the employee's
  matrix, pending acknowledgments and training records.

### Setup for Phase 2

1. Set the **LMS Course** on each Training Requirement taught in Frappe Learning.
2. Add **Competency Checklist Templates** for courses verified by practical demonstration or a
   TRN-704 checklist (e.g. SAF-0024 LOTO, NFPA 70E, SAF-0002 Forklift).
3. Register **Qualified Trainers** and the courses they are authorized for.
4. Make sure each employee's **User ID** on the Employee record is their Learning login.

## Phase 2b: skills and the Frappe HR skill map

- **Skill Definition** (one per Frappe HR Skill): required courses, prerequisite skills (e.g.
  Mechanical before Technician), proficiency when authorized, optional authorization validity,
  and the Training Roles that need the skill (R / C). A role's skills bring their courses, and
  their prerequisites' courses, onto the matrix.
- **Eligibility vs authorization**: Qualified in every course and prerequisite makes the skill
  *Ready for Authorization* and assigns a ToDo to the employee's manager (Reports To, else HR
  Managers). Only a submitted **Skill Authorization** by that manager (or an HR Manager) grants it.
  It cannot be submitted early or by the employee.
- **Lapse**: if a course lapses or a prerequisite is lost, the skill is Lapsed (skills built on it
  too). Once requalified it needs a new authorization.
- **Target skills**: managers set development targets with a date (*Manager → Set Target Skill*).
  Their courses are added as **Dev** rows: tracked with due dates but outside compliance %,
  overdue counts and snapshots.
- **Frappe HR**: the Employee Skill Map shows authorized skills at their proficiency and
  needed skills at zero. Each Designation lists the skills its Training Role requires. Only
  skills with a Skill Definition are managed; other HR skills are untouched.
- **Managers** can open their direct reports' matrices to authorize skills, set targets and
  confirm conditional (C) courses.
- **Skill Matrix** report: employees × skills (A authorized, R ready, T in training, L lapsed).

`hrms` is now a required app.

## Who sees what

Set in **Role Permission Manager**. Any role with *Read* on a Training Matrix DocType (Employee
Training Matrix, Training Record, Competency Evaluation, Skill Authorization) sees every record;
add *Report* to run the Training Matrix, Skill Matrix and Training Requirements Matrix reports.
The Employee role (and the automatic Qualified Trainer role) is scoped instead: employees see
their own records and their direct reports'; trainers also see the records they trained or
evaluated.
