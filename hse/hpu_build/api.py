# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Old endpoint path kept for existing TrulinX sync jobs.

POST /api/method/hse.hpu_build.api.upsert_hpu_units -> hse.shop_qc.api.upsert_qc_units
"""

from hse.shop_qc.api import upsert_qc_units as upsert_hpu_units
