-- Idempotent: rerunning setup never resets training data.
CREATE TABLE IF NOT EXISTS oauth_flows (
  state TEXT PRIMARY KEY, browser TEXT NOT NULL, challenge TEXT NOT NULL,
  proof TEXT NOT NULL, expires INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS tickets (
  ticket TEXT PRIMARY KEY, challenge TEXT NOT NULL, account INTEGER NOT NULL,
  name TEXT NOT NULL, wca_id TEXT NOT NULL, expires INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
  token TEXT PRIMARY KEY, account INTEGER NOT NULL, expires INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_account ON sessions(account);
CREATE TABLE IF NOT EXISTS workspaces (
  account INTEGER PRIMARY KEY, revision INTEGER NOT NULL, payload BLOB NOT NULL
);
