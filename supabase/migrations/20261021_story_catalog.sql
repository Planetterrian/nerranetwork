-- Oct 21 2026: the story catalog (engine/catalog.py, scripts/sync_story_catalog.py).
--
-- What every show aired, item by item, with a story id that follows one story
-- across days and shows; the articles each run fetched (aired or not); the
-- claims ledgers and the corrections. The committed digests remain the record:
-- every row except catalog_articles is rebuilt from the repo by
-- `sync_story_catalog.py --full`, and losing catalog_articles loses a
-- measurement, never an episode. Review:
-- docs/reviews/content_lake_and_story_catalog_2026_10_21.md.
--
-- Tables live in public with a catalog_ prefix so the existing REST client
-- reaches them without exposing a second schema; RLS on, no policies, so only
-- the service role reads or writes (the same rule as every table here).

create table if not exists public.catalog_episodes (
  episode_key text primary key,              -- "<show_slug>:<episode_num>"
  show_slug text not null,
  show_name text,
  episode_num integer not null,
  date date not null,
  title text,
  hook text,
  language text not null default 'en',
  word_count integer,
  item_count integer not null default 0,
  page_url text,
  audio_url text,
  access text not null default 'public',
  updated_at timestamptz not null default now()
);
create index if not exists catalog_episodes_show_date on public.catalog_episodes (show_slug, date);
create index if not exists catalog_episodes_date on public.catalog_episodes (date);

create table if not exists public.catalog_items (
  item_key text primary key,                 -- "<show_slug>:<episode_num>:<position>"
  episode_key text not null references public.catalog_episodes (episode_key) on delete cascade,
  show_slug text not null,
  episode_num integer not null,
  date date not null,
  position integer not null,
  section text,
  title text,
  body text,
  urls text[] not null default '{}',
  kind text not null default 'item',         -- item | also_today | heading | essay
  story_id text,
  tokens text[] not null default '{}',
  language text not null default 'en',
  fts tsvector generated always as (
    to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(body, ''))
  ) stored,
  updated_at timestamptz not null default now()
);
create index if not exists catalog_items_date on public.catalog_items (date);
create index if not exists catalog_items_story on public.catalog_items (story_id);
create index if not exists catalog_items_show_date on public.catalog_items (show_slug, date);
create index if not exists catalog_items_fts on public.catalog_items using gin (fts);

create table if not exists public.catalog_stories (
  story_id text primary key,
  title text,                                -- the first aired item's title
  first_seen date not null,
  last_seen date not null,
  item_count integer not null default 0,
  day_count integer not null default 0,
  show_count integer not null default 0,
  shows text[] not null default '{}',
  updated_at timestamptz not null default now()
);
create index if not exists catalog_stories_last_seen on public.catalog_stories (last_seen);

create table if not exists public.catalog_articles (
  url_key text primary key,                  -- normalised URL (no query, no www)
  url text not null,
  title text,
  outlet text,
  published_date date,
  date_source text,
  first_seen date not null,
  last_seen date not null,
  shows text[] not null default '{}',        -- shows whose runs fetched it
  listed_shows text[] not null default '{}', -- shows whose prompt listed it
  aired boolean not null default false,
  story_id text,
  tokens text[] not null default '{}',
  updated_at timestamptz not null default now()
);
create index if not exists catalog_articles_last_seen on public.catalog_articles (last_seen);
create index if not exists catalog_articles_unaired on public.catalog_articles (last_seen) where not aired;
create index if not exists catalog_articles_story on public.catalog_articles (story_id);

create table if not exists public.catalog_claims (
  claim_key text primary key,                -- "<episode_key>:<ledger id>"
  episode_key text not null references public.catalog_episodes (episode_key) on delete cascade,
  show_slug text not null,
  episode_num integer not null,
  date date not null,
  claim text,
  source_url text,
  source_title text,
  supporting_quote text,
  status text,
  updated_at timestamptz not null default now()
);
create index if not exists catalog_claims_episode on public.catalog_claims (episode_key);
create index if not exists catalog_claims_status on public.catalog_claims (status);

create table if not exists public.catalog_corrections (
  correction_key text primary key,           -- "<show_slug>:<episode>:<date>:<n>"
  show_slug text not null,
  episode_num integer not null,
  date date not null,
  text text not null,
  where_ text,
  story_ids text[] not null default '{}',
  updated_at timestamptz not null default now()
);

alter table public.catalog_episodes enable row level security;
alter table public.catalog_items enable row level security;
alter table public.catalog_stories enable row level security;
alter table public.catalog_articles enable row level security;
alter table public.catalog_claims enable row level security;
alter table public.catalog_corrections enable row level security;
