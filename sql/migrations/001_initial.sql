CREATE TABLE IF NOT EXISTS listings (
  listing_id TEXT PRIMARY KEY,
  source TEXT NOT NULL DEFAULT 'rentcast',
  address TEXT,
  city TEXT,
  state TEXT,
  zip TEXT,
  latitude DOUBLE PRECISION,
  longitude DOUBLE PRECISION,
  price NUMERIC,
  bedrooms INTEGER,
  bathrooms NUMERIC,
  square_feet INTEGER,
  year_built INTEGER,
  description TEXT,
  distress_score NUMERIC,
  distress_keywords TEXT[],
  raw JSONB,
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  enriched_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS listings_distress_idx ON listings (distress_score DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS listings_zip_idx ON listings (zip);
