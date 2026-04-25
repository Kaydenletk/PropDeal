CREATE TABLE IF NOT EXISTS listings (
    listing_id          TEXT PRIMARY KEY,
    city                TEXT NOT NULL,
    state               TEXT NOT NULL,
    address             TEXT NOT NULL,
    price               INTEGER NOT NULL,
    bedrooms            SMALLINT,
    bathrooms           NUMERIC(3, 1),
    sqft                INTEGER,
    year_built          SMALLINT,
    description         TEXT,
    latitude            NUMERIC(10, 7),
    longitude           NUMERIC(10, 7),
    distress_score      NUMERIC(3, 2),
    discount_percent    NUMERIC(5, 2),
    estimated_rent      INTEGER,
    cap_rate            NUMERIC(5, 2),
    final_score         NUMERIC(5, 2),
    ingested_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_listings_city       ON listings(city);
CREATE INDEX IF NOT EXISTS idx_listings_score      ON listings(final_score DESC);
CREATE INDEX IF NOT EXISTS idx_listings_ingested   ON listings(ingested_at DESC);

CREATE TABLE IF NOT EXISTS macro_indicators (
    recorded_date       DATE PRIMARY KEY,
    mortgage_rate_30yr  NUMERIC(5, 3),
    cpi                 NUMERIC(8, 3),
    unemployment_rate   NUMERIC(4, 2)
);
