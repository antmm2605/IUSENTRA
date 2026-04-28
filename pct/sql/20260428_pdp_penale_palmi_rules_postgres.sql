-- PDP Penale: stati canonici e regole locali ufficio.
ALTER TABLE criminal_cases ADD COLUMN IF NOT EXISTS current_ministry_status_canonical TEXT;
ALTER TABLE criminal_cases ADD COLUMN IF NOT EXISTS local_office_rule_source TEXT;
ALTER TABLE criminal_access_requests ADD COLUMN IF NOT EXISTS ministry_status_canonical TEXT;

