# Stage 2: handlers, installer and reporting (not activated)

Adds source and Service Request Register. Does not modify hooks.py, deploy, enable,
grant roles, configure SLA/assignment rules, or modify the Default template.
Report access requires enabled settings and an internal agent; get_list respects
HD Ticket document permission conditions. Test team isolation on the installed version.

Pending repair insertion uses standard permissions and may mark Asset Out of Order.
Triage explicitly acknowledges that standard behavior. No automatic submission,
capitalization, stock issue, contractor emails/accounts, or safety finding closure.
The installer is idempotent and defaults the HD Settings feature switch OFF.
configure_template is an explicit System Manager operation, not a migration side effect.
Internal fields use permission level 8 plus Agents template visibility. Asset lookup
remains subject to standard Asset read permissions. Do not grant broad roles blindly.

Separate hook review must wire HD Ticket validate/on_update to events.validate/on_update,
Asset Repair validate to events.validate_repair, and before_cancel/on_trash to
events.protect_repair_removal. Add install.after_migrate to existing installation and
migration lists without replacing other hooks. Do not enable before site tests.

Native resolved status and closed work stage enforce triage, verification, submitted
completed repair, and restoration when an outage exists. Manager-reasoned duplicate
or cancellation exceptions retain repair history. Reopening clears verification.
Cancelled-repair replacement/amendment workflow is not implemented; keep affected
requests open pending supervised correction. Linking existing repairs is an authorized
API, not a Helpdesk SPA button. No automatic repair-to-ticket closure synchronization.

Register includes category chart, request count, distinct linked repairs, overdue
providers, actual per-ticket outage hours and provider elapsed hours. Missing durations
remain missing. Shared/overlapping outages are not consolidated; do not sum into
asset availability/MTBF. No cost/labor/repeat-failure reports or standalone dashboard yet.

Local syntax/mock checks are not Frappe site tests. Before deployment/activation:
verify installed Helpdesk schema and report sync, migrate twice, test employee/API
permissions, ordinary email intake, native closure/reopening, concurrent repair creation,
permission-failure rollback, shared repairs, cancellation, non-asset exceptions,
template isolation and team-restricted reports. Site acceptance is still required.
