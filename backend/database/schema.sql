PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS projects (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  title             TEXT NOT NULL,
  original_filename TEXT NOT NULL,
  date              TEXT NOT NULL,
  rel_dir           TEXT NOT NULL,
  duration          REAL,
  file_size         INTEGER,
  status            TEXT NOT NULL,
  error_message     TEXT,
  video_url         TEXT,
  created_at        TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS chunks (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id    INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  chunk_index   INTEGER NOT NULL,
  filename      TEXT NOT NULL,
  file_size     INTEGER,
  status        TEXT NOT NULL,
  retry_count   INTEGER NOT NULL DEFAULT 0,
  error_message TEXT,
  UNIQUE(project_id, chunk_index)
);

CREATE TABLE IF NOT EXISTS transcripts (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  chunk_index INTEGER NOT NULL,
  content     TEXT NOT NULL,
  UNIQUE(project_id, chunk_index)
);

CREATE TABLE IF NOT EXISTS analyses (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id       INTEGER NOT NULL UNIQUE REFERENCES projects(id) ON DELETE CASCADE,
  overall_summary  TEXT,
  key_points       TEXT,
  detailed_summary TEXT,
  decisions        TEXT,
  todos            TEXT,
  important        TEXT,
  extracted_info   TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS transcripts_fts USING fts5(
  content,
  project_id UNINDEXED,
  content='transcripts',
  content_rowid='id',
  tokenize='unicode61'
);

CREATE VIRTUAL TABLE IF NOT EXISTS analyses_fts USING fts5(
  overall_summary,
  key_points,
  detailed_summary,
  decisions,
  todos,
  important,
  project_id UNINDEXED,
  content='analyses',
  content_rowid='id',
  tokenize='unicode61'
);

CREATE TRIGGER IF NOT EXISTS transcripts_ai AFTER INSERT ON transcripts BEGIN
  INSERT INTO transcripts_fts(rowid, content, project_id)
  VALUES (new.id, new.content, new.project_id);
END;

CREATE TRIGGER IF NOT EXISTS transcripts_ad AFTER DELETE ON transcripts BEGIN
  INSERT INTO transcripts_fts(transcripts_fts, rowid, content, project_id)
  VALUES ('delete', old.id, old.content, old.project_id);
END;

CREATE TRIGGER IF NOT EXISTS transcripts_au AFTER UPDATE ON transcripts BEGIN
  INSERT INTO transcripts_fts(transcripts_fts, rowid, content, project_id)
  VALUES ('delete', old.id, old.content, old.project_id);
  INSERT INTO transcripts_fts(rowid, content, project_id)
  VALUES (new.id, new.content, new.project_id);
END;

CREATE TRIGGER IF NOT EXISTS analyses_ai AFTER INSERT ON analyses BEGIN
  INSERT INTO analyses_fts(
    rowid, overall_summary, key_points, detailed_summary, decisions, todos, important, project_id
  ) VALUES (
    new.id, new.overall_summary, new.key_points, new.detailed_summary,
    new.decisions, new.todos, new.important, new.project_id
  );
END;

CREATE TRIGGER IF NOT EXISTS analyses_ad AFTER DELETE ON analyses BEGIN
  INSERT INTO analyses_fts(analyses_fts, rowid, overall_summary, key_points, detailed_summary, decisions, todos, important, project_id)
  VALUES (
    'delete', old.id, old.overall_summary, old.key_points, old.detailed_summary,
    old.decisions, old.todos, old.important, old.project_id
  );
END;

CREATE TRIGGER IF NOT EXISTS analyses_au AFTER UPDATE ON analyses BEGIN
  INSERT INTO analyses_fts(analyses_fts, rowid, overall_summary, key_points, detailed_summary, decisions, todos, important, project_id)
  VALUES (
    'delete', old.id, old.overall_summary, old.key_points, old.detailed_summary,
    old.decisions, old.todos, old.important, old.project_id
  );
  INSERT INTO analyses_fts(
    rowid, overall_summary, key_points, detailed_summary, decisions, todos, important, project_id
  ) VALUES (
    new.id, new.overall_summary, new.key_points, new.detailed_summary,
    new.decisions, new.todos, new.important, new.project_id
  );
END;

CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
CREATE INDEX IF NOT EXISTS idx_projects_date ON projects(date);
CREATE INDEX IF NOT EXISTS idx_chunks_project ON chunks(project_id, chunk_index);
