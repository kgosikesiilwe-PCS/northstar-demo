PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL UNIQUE,
  phone TEXT,
  full_name TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'user',
  mfa_enabled INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_login_at TEXT
);

CREATE TABLE IF NOT EXISTS beneficiary_profiles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  owner_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  full_name TEXT NOT NULL,
  preferred_name TEXT,
  date_of_birth TEXT,
  address_line_1 TEXT,
  address_line_2 TEXT,
  city TEXT,
  state TEXT,
  zip TEXT,
  phone TEXT,
  email TEXT,
  preferred_language TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_reviewed_at TEXT
);

CREATE TABLE IF NOT EXISTS trusted_people (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  beneficiary_profile_id INTEGER NOT NULL REFERENCES beneficiary_profiles(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  relationship TEXT NOT NULL,
  phone TEXT,
  email TEXT,
  address TEXT,
  is_emergency_contact INTEGER NOT NULL DEFAULT 0,
  priority_order INTEGER NOT NULL DEFAULT 1,
  invite_token TEXT UNIQUE,
  invite_status TEXT NOT NULL DEFAULT 'created',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS access_grants (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  beneficiary_profile_id INTEGER NOT NULL REFERENCES beneficiary_profiles(id) ON DELETE CASCADE,
  trusted_person_id INTEGER NOT NULL REFERENCES trusted_people(id) ON DELETE CASCADE,
  recipient_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
  access_level TEXT NOT NULL DEFAULT 'viewer',
  allowed_sections TEXT NOT NULL DEFAULT '[]',
  can_view INTEGER NOT NULL DEFAULT 1,
  can_edit INTEGER NOT NULL DEFAULT 0,
  can_upload INTEGER NOT NULL DEFAULT 0,
  can_download INTEGER NOT NULL DEFAULT 0,
  expires_at TEXT,
  revoked_at TEXT,
  authorization_text_version TEXT NOT NULL DEFAULT 'family-access-v1',
  electronic_signature TEXT,
  signed_at TEXT,
  created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS medications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  beneficiary_profile_id INTEGER NOT NULL REFERENCES beneficiary_profiles(id) ON DELETE CASCADE,
  pharmacy_name TEXT,
  pharmacy_phone TEXT,
  medication_name TEXT NOT NULL,
  dosage TEXT,
  frequency TEXT,
  prescribing_doctor TEXT,
  reason TEXT,
  start_date TEXT,
  notes TEXT,
  source TEXT,
  last_confirmed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS allergies (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  beneficiary_profile_id INTEGER NOT NULL REFERENCES beneficiary_profiles(id) ON DELETE CASCADE,
  allergy_type TEXT NOT NULL,
  allergy_name TEXT NOT NULL,
  reaction TEXT,
  severity TEXT,
  notes TEXT,
  source TEXT,
  last_confirmed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS insurance_policies (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  beneficiary_profile_id INTEGER NOT NULL REFERENCES beneficiary_profiles(id) ON DELETE CASCADE,
  policy_type TEXT NOT NULL,
  insurance_company TEXT,
  plan_name TEXT,
  plan_number TEXT,
  member_id_encrypted TEXT,
  rx_bin_encrypted TEXT,
  rx_pcn_encrypted TEXT,
  group_number_encrypted TEXT,
  effective_date TEXT,
  notes TEXT,
  source TEXT,
  last_confirmed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS providers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  beneficiary_profile_id INTEGER NOT NULL REFERENCES beneficiary_profiles(id) ON DELETE CASCADE,
  provider_type TEXT NOT NULL,
  name TEXT NOT NULL,
  practice_name TEXT,
  specialty TEXT,
  address TEXT,
  phone TEXT,
  fax TEXT,
  doctor_network TEXT,
  patient_portal_url TEXT,
  last_visit_date TEXT,
  next_appointment_date TEXT,
  is_pcp INTEGER NOT NULL DEFAULT 0,
  source TEXT,
  last_confirmed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS medicare_advisors (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  beneficiary_profile_id INTEGER NOT NULL REFERENCES beneficiary_profiles(id) ON DELETE CASCADE,
  advisor_name TEXT,
  agency_name TEXT,
  phone TEXT,
  email TEXT,
  npn TEXT,
  insurance_company TEXT,
  plan_name TEXT,
  last_helped_date TEXT,
  notes TEXT,
  source TEXT,
  last_confirmed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS surgeries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  beneficiary_profile_id INTEGER NOT NULL REFERENCES beneficiary_profiles(id) ON DELETE CASCADE,
  surgery_name TEXT NOT NULL,
  approximate_date TEXT,
  facility TEXT,
  doctor TEXT,
  notes TEXT,
  source TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS documents (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  beneficiary_profile_id INTEGER NOT NULL REFERENCES beneficiary_profiles(id) ON DELETE CASCADE,
  document_type TEXT NOT NULL,
  display_name TEXT NOT NULL,
  original_filename TEXT,
  encrypted_filename TEXT,
  file_sha256 TEXT,
  file_size INTEGER,
  mime_type TEXT,
  document_location_text TEXT,
  notes TEXT,
  uploaded_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
  access_section TEXT NOT NULL DEFAULT 'documents',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS important_notes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  beneficiary_profile_id INTEGER NOT NULL REFERENCES beneficiary_profiles(id) ON DELETE CASCADE,
  category TEXT NOT NULL,
  note_text_encrypted TEXT NOT NULL,
  created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS financial_locators (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  beneficiary_profile_id INTEGER NOT NULL REFERENCES beneficiary_profiles(id) ON DELETE CASCADE,
  category TEXT NOT NULL,
  institution_name TEXT NOT NULL,
  contact_phone TEXT,
  website TEXT,
  last_four_only_encrypted TEXT,
  document_location TEXT,
  trusted_contact TEXT,
  notes_encrypted TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  actor_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
  beneficiary_profile_id INTEGER REFERENCES beneficiary_profiles(id) ON DELETE CASCADE,
  action TEXT NOT NULL,
  section TEXT,
  record_id INTEGER,
  ip_address TEXT,
  device_info TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_profiles_owner ON beneficiary_profiles(owner_user_id);
CREATE INDEX IF NOT EXISTS idx_access_grants_recipient ON access_grants(recipient_user_id);
CREATE INDEX IF NOT EXISTS idx_access_grants_profile ON access_grants(beneficiary_profile_id);
CREATE INDEX IF NOT EXISTS idx_audit_profile ON audit_logs(beneficiary_profile_id);
CREATE INDEX IF NOT EXISTS idx_documents_profile ON documents(beneficiary_profile_id);

CREATE TABLE IF NOT EXISTS medicare_cards (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  beneficiary_profile_id INTEGER NOT NULL REFERENCES beneficiary_profiles(id) ON DELETE CASCADE,
  mbi_encrypted TEXT,
  name_on_card TEXT,
  part_a_date TEXT,
  part_b_date TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(beneficiary_profile_id)
);
