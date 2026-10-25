# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from hse.training_matrix.matrix import enqueue_resync
from hse.training_matrix.skill_status import dependency_order
from hse.training_matrix.skills import definitions


class SkillDefinition(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from hse.training_matrix.doctype.skill_definition_course.skill_definition_course import (
			SkillDefinitionCourse,
		)
		from hse.training_matrix.doctype.skill_definition_prerequisite.skill_definition_prerequisite import (
			SkillDefinitionPrerequisite,
		)
		from hse.training_matrix.doctype.skill_definition_role.skill_definition_role import (
			SkillDefinitionRole,
		)

		authorization_valid_months: DF.Int
		authorizer_role: DF.Link | None
		courses: DF.Table[SkillDefinitionCourse]
		description: DF.SmallText | None
		disabled: DF.Check
		prerequisites: DF.TableMultiSelect[SkillDefinitionPrerequisite]
		proficiency: DF.Rating | None
		roles: DF.Table[SkillDefinitionRole]
		skill: DF.Link
	# end: auto-generated types

	def validate(self):
		if not self.courses and not self.prerequisites:
			frappe.throw(_("Add at least one required course or prerequisite skill."))
		for table, field in (
			("courses", "training_requirement"),
			("roles", "training_role"),
			("prerequisites", "skill"),
		):
			seen = set()
			for row in self.get(table):
				if row.get(field) in seen:
					frappe.throw(_("{0} is listed more than once.").format(frappe.bold(row.get(field))))
				seen.add(row.get(field))
		if any(p.skill == self.skill for p in self.prerequisites):
			frappe.throw(_("A skill cannot be its own prerequisite."))
		defs = definitions()
		defs[self.skill] = {
			"courses": [c.training_requirement for c in self.courses],
			"prerequisites": [p.skill for p in self.prerequisites],
		}
		try:
			dependency_order(defs, [self.skill])
		except ValueError as e:
			frappe.throw(str(e))
		self.check_prerequisites_defined(defs)

	def check_prerequisites_defined(self, defs):
		for p in self.prerequisites:
			if p.skill not in defs:
				frappe.throw(
					_("Prerequisite {0} needs its own Skill Definition first.").format(frappe.bold(p.skill))
				)

	def on_update(self):
		if not self.flags.skip_resync:
			enqueue_resync()

	def on_trash(self):
		if frappe.db.exists(
			"Skill Definition Prerequisite", {"skill": self.skill, "parenttype": "Skill Definition"}
		):
			frappe.throw(_("{0} is a prerequisite of another skill.").format(frappe.bold(self.skill)))
		enqueue_resync()
