ALTER TABLE users ADD COLUMN slot_bypass BOOLEAN NOT NULL DEFAULT FALSE;
UPDATE users SET slot_bypass = TRUE WHERE role = 'admin';
