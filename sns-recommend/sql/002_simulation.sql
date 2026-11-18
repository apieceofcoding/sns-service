CREATE TABLE IF NOT EXISTS simulation (
 only_row boolean PRIMARY KEY DEFAULT true CHECK (only_row),
 shifted boolean NOT NULL
);
