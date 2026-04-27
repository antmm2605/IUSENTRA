CREATE TABLE IF NOT EXISTS site_studio (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_slug TEXT NOT NULL UNIQUE,
    studio_nome TEXT NOT NULL DEFAULT '',
    site_name TEXT NOT NULL,
    public_slug TEXT NOT NULL UNIQUE,
    site_title TEXT NOT NULL DEFAULT '',
    site_description TEXT NOT NULL DEFAULT '',
    hero_claim TEXT NOT NULL DEFAULT '',
    logo_url TEXT NOT NULL DEFAULT '',
    favicon_url TEXT NOT NULL DEFAULT '',
    primary_color TEXT NOT NULL DEFAULT '#1d4ed8',
    secondary_color TEXT NOT NULL DEFAULT '#0f172a',
    accent_color TEXT NOT NULL DEFAULT '#16a34a',
    contact_email TEXT NOT NULL DEFAULT '',
    contact_phone TEXT NOT NULL DEFAULT '',
    whatsapp_number TEXT NOT NULL DEFAULT '',
    address TEXT NOT NULL DEFAULT '',
    city TEXT NOT NULL DEFAULT '',
    province TEXT NOT NULL DEFAULT '',
    zip_code TEXT NOT NULL DEFAULT '',
    footer_text TEXT NOT NULL DEFAULT '',
    facebook_url TEXT NOT NULL DEFAULT '',
    instagram_url TEXT NOT NULL DEFAULT '',
    linkedin_url TEXT NOT NULL DEFAULT '',
    show_legal_tools INTEGER NOT NULL DEFAULT 0,
    show_applications INTEGER NOT NULL DEFAULT 0,
    show_legal_news INTEGER NOT NULL DEFAULT 0,
    is_published INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    theme_template TEXT NOT NULL DEFAULT 'classic_legal',
    theme_variant TEXT NOT NULL DEFAULT 'default',
    design_tokens_json TEXT NOT NULL DEFAULT '{}',
    typography_json TEXT NOT NULL DEFAULT '{}',
    layout_json TEXT NOT NULL DEFAULT '{}',
    effects_json TEXT NOT NULL DEFAULT '{}',
    custom_css TEXT NOT NULL DEFAULT '',
    cookie_banner_enabled INTEGER NOT NULL DEFAULT 0,
    analytics_enabled INTEGER NOT NULL DEFAULT 0,
    analytics_provider TEXT NOT NULL DEFAULT '',
    analytics_id TEXT NOT NULL DEFAULT '',
    seo_json TEXT NOT NULL DEFAULT '{}',
    legal_disclaimer TEXT NOT NULL DEFAULT '',
    privacy_url TEXT NOT NULL DEFAULT '',
    cookie_policy_url TEXT NOT NULL DEFAULT '',
    accessibility_statement_url TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_site_studio_public_slug ON site_studio(public_slug);
CREATE INDEX IF NOT EXISTS idx_site_studio_published ON site_studio(is_published, is_active);

CREATE TABLE IF NOT EXISTS site_page (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    slug TEXT NOT NULL,
    excerpt TEXT NOT NULL DEFAULT '',
    body_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'draft',
    show_in_menu INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_home INTEGER NOT NULL DEFAULT 0,
    seo_title TEXT NOT NULL DEFAULT '',
    seo_description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (site_id) REFERENCES site_studio(id) ON DELETE CASCADE,
    UNIQUE(site_id, slug)
);

CREATE INDEX IF NOT EXISTS idx_site_page_site_status ON site_page(site_id, status, sort_order);
CREATE INDEX IF NOT EXISTS idx_site_page_home ON site_page(site_id, is_home);

CREATE TABLE IF NOT EXISTS site_article (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    slug TEXT NOT NULL,
    excerpt TEXT NOT NULL DEFAULT '',
    cover_url TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT '',
    tags_csv TEXT NOT NULL DEFAULT '',
    author_name TEXT NOT NULL DEFAULT '',
    body_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'draft',
    published_at TEXT NOT NULL DEFAULT '',
    seo_title TEXT NOT NULL DEFAULT '',
    seo_description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (site_id) REFERENCES site_studio(id) ON DELETE CASCADE,
    UNIQUE(site_id, slug)
);

CREATE INDEX IF NOT EXISTS idx_site_article_site_status ON site_article(site_id, status, published_at);

CREATE TABLE IF NOT EXISTS site_service (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    slug TEXT NOT NULL,
    short_description TEXT NOT NULL DEFAULT '',
    long_description TEXT NOT NULL DEFAULT '',
    icon TEXT NOT NULL DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_visible INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (site_id) REFERENCES site_studio(id) ON DELETE CASCADE,
    UNIQUE(site_id, slug)
);

CREATE TABLE IF NOT EXISTS site_professional (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id INTEGER NOT NULL,
    full_name TEXT NOT NULL,
    role_title TEXT NOT NULL DEFAULT '',
    bio TEXT NOT NULL DEFAULT '',
    photo_url TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_visible INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (site_id) REFERENCES site_studio(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS site_office (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    address TEXT NOT NULL DEFAULT '',
    city TEXT NOT NULL DEFAULT '',
    province TEXT NOT NULL DEFAULT '',
    zip_code TEXT NOT NULL DEFAULT '',
    lat TEXT NOT NULL DEFAULT '',
    lng TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    opening_hours TEXT NOT NULL DEFAULT '',
    map_url TEXT NOT NULL DEFAULT '',
    is_primary INTEGER NOT NULL DEFAULT 0,
    is_visible INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (site_id) REFERENCES site_studio(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS site_booking_rule (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id INTEGER NOT NULL,
    office_id INTEGER NOT NULL,
    weekday INTEGER NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    slot_minutes INTEGER NOT NULL DEFAULT 30,
    max_requests_per_slot INTEGER NOT NULL DEFAULT 1,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (site_id) REFERENCES site_studio(id) ON DELETE CASCADE,
    FOREIGN KEY (office_id) REFERENCES site_office(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_site_booking_rule_site ON site_booking_rule(site_id, office_id, weekday, is_active);

CREATE TABLE IF NOT EXISTS site_booking_request (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id INTEGER NOT NULL,
    office_id INTEGER,
    customer_name TEXT NOT NULL,
    customer_email TEXT NOT NULL,
    customer_phone TEXT NOT NULL DEFAULT '',
    requested_date TEXT NOT NULL,
    requested_time TEXT NOT NULL,
    subject TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    privacy_accepted INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    agenda_event_id TEXT NOT NULL DEFAULT '',
    reviewed_by TEXT NOT NULL DEFAULT '',
    reviewed_at TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (site_id) REFERENCES site_studio(id) ON DELETE CASCADE,
    FOREIGN KEY (office_id) REFERENCES site_office(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_site_booking_request_site_status ON site_booking_request(site_id, status, requested_date, requested_time);

CREATE TABLE IF NOT EXISTS site_contact_submission (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id INTEGER NOT NULL,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT NOT NULL DEFAULT '',
    subject TEXT NOT NULL DEFAULT '',
    message TEXT NOT NULL,
    privacy_accepted INTEGER NOT NULL DEFAULT 0,
    lead_cliente_id TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (site_id) REFERENCES site_studio(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_site_contact_submission_site ON site_contact_submission(site_id, created_at);

CREATE TABLE IF NOT EXISTS site_theme_preset (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT '',
    preview_image_url TEXT NOT NULL DEFAULT '',
    tokens_json TEXT NOT NULL DEFAULT '{}',
    blocks_seed_json TEXT NOT NULL DEFAULT '[]',
    is_builtin INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS site_design_revision (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id INTEGER NOT NULL,
    label TEXT NOT NULL DEFAULT '',
    snapshot_json TEXT NOT NULL DEFAULT '{}',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (site_id) REFERENCES site_studio(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_site_design_revision_site ON site_design_revision(site_id, created_at);
