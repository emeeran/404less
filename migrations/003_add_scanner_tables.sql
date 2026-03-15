-- Migration: 003_add_scanner_tables
-- @spec FEAT-001/DM-001 (Scan)
-- @spec FEAT-001/DM-002 (Link)

-- Create scans table
CREATE TABLE IF NOT EXISTS scans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url VARCHAR(2048) NOT NULL,
    depth INTEGER NOT NULL CHECK (depth >= 1 AND depth <= 10),
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'stopped', 'failed')),
    respect_robots BOOLEAN NOT NULL DEFAULT TRUE,
    user_agent VARCHAR(256),
    total_links INTEGER NOT NULL DEFAULT 0,
    checked_links INTEGER NOT NULL DEFAULT 0,
    broken_links INTEGER NOT NULL DEFAULT 0,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    error_message TEXT,

    CONSTRAINT valid_scan_url CHECK (url ~* '^https?://')
);

CREATE INDEX IF NOT EXISTS idx_scans_status ON scans(status);
CREATE INDEX IF NOT EXISTS idx_scans_created_at ON scans(created_at);

-- Create links table
CREATE TABLE IF NOT EXISTS links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_id UUID NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    url VARCHAR(2048) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'ok', 'broken', 'skipped')),
    status_code INTEGER,
    error VARCHAR(512),
    depth INTEGER NOT NULL,
    parent_url VARCHAR(2048),
    checked_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_link_url CHECK (url ~* '^https?://')
);

CREATE INDEX IF NOT EXISTS idx_links_scan_id ON links(scan_id);
CREATE INDEX IF NOT EXISTS idx_links_scan_status ON links(scan_id, status);
CREATE INDEX IF NOT EXISTS idx_links_scan_depth ON links(scan_id, depth);
CREATE UNIQUE INDEX IF NOT EXISTS idx_links_scan_url_unique ON links(scan_id, url);

-- Comments for documentation
COMMENT ON TABLE scans IS '@spec FEAT-001/DM-001 - Scan jobs for broken link detection';
COMMENT ON TABLE links IS '@spec FEAT-001/DM-002 - Discovered links within a scan';
COMMENT ON COLUMN scans.depth IS '@spec FEAT-001/C-005 - Maximum crawl depth is 10';
COMMENT ON COLUMN scans.status IS '@spec FEAT-001/DM-001 - pending, running, completed, stopped, failed';
COMMENT ON COLUMN links.status IS '@spec FEAT-001/DM-002 - pending, ok, broken, skipped';
COMMENT ON INDEX idx_links_scan_url_unique IS '@spec FEAT-001/EC-004 - URL deduplication per scan';
