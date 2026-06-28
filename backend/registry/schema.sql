-- Entity Registry Database Schema
-- SQLite database for canonical entity lookup and deduplication

-- Main entities table (canonical entities)
CREATE TABLE IF NOT EXISTS entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    confidence REAL DEFAULT 0.5 CHECK(confidence >= 0.0 AND confidence <= 1.0),
    mention_count INTEGER DEFAULT 1,
    relation_count INTEGER DEFAULT 0,
    first_seen_doc TEXT,
    last_seen_doc TEXT,
    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    embedding BLOB,  -- Cached vector embedding
    metadata TEXT,   -- JSON blob for extra properties
    validated BOOLEAN DEFAULT 0,  -- Human validated
    UNIQUE(canonical_name, entity_type)
);

-- Entity aliases/variants table
CREATE TABLE IF NOT EXISTS entity_aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id INTEGER NOT NULL,
    alias_name TEXT NOT NULL,
    alias_type TEXT DEFAULT 'variant',  -- 'variant', 'abbreviation', 'translation', 'misspelling'
    confidence REAL DEFAULT 0.7,
    source TEXT DEFAULT 'learned',      -- 'learned', 'manual', 'seed'
    language TEXT,                      -- 'fr', 'ar', 'en'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE,
    UNIQUE(entity_id, alias_name)
);

-- Validation decisions (human-in-the-loop)
CREATE TABLE IF NOT EXISTS validation_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity1_id INTEGER NOT NULL,
    entity2_id INTEGER NOT NULL,
    decision TEXT NOT NULL CHECK(decision IN ('merge', 'separate', 'pending')),
    similarity_score REAL,
    reason TEXT,
    decided_by TEXT DEFAULT 'auto',     -- 'auto', 'user:{username}'
    decided_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (entity1_id) REFERENCES entities(id) ON DELETE CASCADE,
    FOREIGN KEY (entity2_id) REFERENCES entities(id) ON DELETE CASCADE
);

-- Relation patterns learned from documents
CREATE TABLE IF NOT EXISTS relation_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    relation_type TEXT NOT NULL,
    source_entity_type TEXT NOT NULL,
    target_entity_type TEXT NOT NULL,
    pattern_text TEXT,                  -- "X is CEO of Y", "X owns Y"
    confidence REAL DEFAULT 0.5,
    seen_count INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(relation_type, source_entity_type, target_entity_type, pattern_text)
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_canonical_name ON entities(canonical_name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_entity_type ON entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_confidence ON entities(confidence);
CREATE INDEX IF NOT EXISTS idx_mention_count ON entities(mention_count DESC);

CREATE INDEX IF NOT EXISTS idx_alias_name ON entity_aliases(alias_name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_alias_entity ON entity_aliases(entity_id);
CREATE INDEX IF NOT EXISTS idx_alias_source ON entity_aliases(source);

CREATE INDEX IF NOT EXISTS idx_validation_decision ON validation_decisions(decision);
CREATE INDEX IF NOT EXISTS idx_validation_entities ON validation_decisions(entity1_id, entity2_id);

-- Full-text search on entity names (optional, for advanced search)
CREATE VIRTUAL TABLE IF NOT EXISTS entities_fts USING fts5(
    canonical_name,
    entity_type,
    content=entities,
    content_rowid=id
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS entities_ai AFTER INSERT ON entities BEGIN
  INSERT INTO entities_fts(rowid, canonical_name, entity_type)
  VALUES (new.id, new.canonical_name, new.entity_type);
END;

CREATE TRIGGER IF NOT EXISTS entities_ad AFTER DELETE ON entities BEGIN
  DELETE FROM entities_fts WHERE rowid = old.id;
END;

CREATE TRIGGER IF NOT EXISTS entities_au AFTER UPDATE ON entities BEGIN
  UPDATE entities_fts
  SET canonical_name = new.canonical_name, entity_type = new.entity_type
  WHERE rowid = old.id;
END;

-- Trigger to update last_updated timestamp
CREATE TRIGGER IF NOT EXISTS entities_update_timestamp AFTER UPDATE ON entities
FOR EACH ROW
BEGIN
  UPDATE entities SET last_updated = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;
