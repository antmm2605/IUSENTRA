-- PDP Penale: stati canonici e regole locali ufficio.
ALTER TABLE criminal_cases ADD COLUMN current_ministry_status_canonical TEXT;
ALTER TABLE criminal_cases ADD COLUMN local_office_rule_source TEXT;
ALTER TABLE criminal_access_requests ADD COLUMN ministry_status_canonical TEXT;

