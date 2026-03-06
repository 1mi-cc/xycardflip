-- Supabase mirror schema for Card Flip Assistant
-- Default prefix matches SUPABASE_TABLE_PREFIX=cardflip_
-- Run this in Supabase SQL Editor before enabling sync.

create table if not exists public.cardflip_sales_raw (
  id bigint primary key,
  source text not null,
  item_id text,
  title text not null,
  description text default '',
  sold_price double precision not null,
  sold_at text not null,
  raw_json text not null,
  created_at text not null
);

create table if not exists public.cardflip_listings_raw (
  id bigint primary key,
  source text not null,
  listing_id text,
  seller_id text,
  title text not null,
  description text default '',
  list_price double precision not null,
  listed_at text not null,
  status text not null,
  raw_json text not null,
  created_at text not null
);

create table if not exists public.cardflip_item_features (
  id bigint primary key,
  ref_type text not null,
  ref_id bigint not null,
  card_name text not null,
  rarity text not null,
  edition text not null,
  card_condition text not null,
  extras_json text not null,
  confidence double precision not null,
  extracted_by text not null,
  extracted_at text not null
);

create table if not exists public.cardflip_valuation_records (
  id bigint primary key,
  listing_row_id bigint not null,
  expected_sale_price double precision not null,
  buy_limit double precision not null,
  suggested_list_price double precision not null,
  ci_low double precision not null,
  ci_high double precision not null,
  model_confidence double precision not null,
  comparables_count integer not null,
  reasoning text not null,
  created_at text not null
);

create table if not exists public.cardflip_opportunities (
  id bigint primary key,
  listing_row_id bigint not null,
  valuation_id bigint not null,
  expected_profit double precision not null,
  roi double precision not null,
  score double precision not null,
  status text not null,
  created_at text not null,
  reviewed_at text,
  review_note text default ''
);

create table if not exists public.cardflip_trades (
  id bigint primary key,
  opportunity_id bigint not null,
  status text not null,
  approved_buy_price double precision not null,
  target_sell_price double precision not null,
  approved_by text not null,
  listing_url text default '',
  sold_price double precision,
  note text default '',
  created_at text not null,
  updated_at text not null
);

create table if not exists public.cardflip_execution_logs (
  id bigint primary key,
  trade_id bigint not null,
  action text not null,
  provider text not null,
  dry_run integer not null,
  request_json text not null,
  response_json text not null,
  success integer not null,
  error text not null,
  created_at text not null
);

create table if not exists public.cardflip_opportunity_reject_logs (
  id bigint primary key,
  opportunity_id bigint not null,
  listing_row_id bigint not null,
  reject_mode text not null,
  note text not null,
  snapshot_json text not null,
  created_at text not null
);

create index if not exists idx_cardflip_listings_raw_status
  on public.cardflip_listings_raw(status);
create index if not exists idx_cardflip_opportunities_status
  on public.cardflip_opportunities(status);
create index if not exists idx_cardflip_execution_logs_trade_id
  on public.cardflip_execution_logs(trade_id);
create index if not exists idx_cardflip_execution_logs_action
  on public.cardflip_execution_logs(action);

-- Security hardening for public schema tables.
-- Backend sync uses service_role key, so enable RLS and block anon/authenticated.
alter table public.cardflip_sales_raw enable row level security;
alter table public.cardflip_listings_raw enable row level security;
alter table public.cardflip_item_features enable row level security;
alter table public.cardflip_valuation_records enable row level security;
alter table public.cardflip_opportunities enable row level security;
alter table public.cardflip_trades enable row level security;
alter table public.cardflip_execution_logs enable row level security;
alter table public.cardflip_opportunity_reject_logs enable row level security;

revoke all on table public.cardflip_sales_raw from anon, authenticated;
revoke all on table public.cardflip_listings_raw from anon, authenticated;
revoke all on table public.cardflip_item_features from anon, authenticated;
revoke all on table public.cardflip_valuation_records from anon, authenticated;
revoke all on table public.cardflip_opportunities from anon, authenticated;
revoke all on table public.cardflip_trades from anon, authenticated;
revoke all on table public.cardflip_execution_logs from anon, authenticated;
revoke all on table public.cardflip_opportunity_reject_logs from anon, authenticated;

grant select, insert, update, delete on table public.cardflip_sales_raw to service_role;
grant select, insert, update, delete on table public.cardflip_listings_raw to service_role;
grant select, insert, update, delete on table public.cardflip_item_features to service_role;
grant select, insert, update, delete on table public.cardflip_valuation_records to service_role;
grant select, insert, update, delete on table public.cardflip_opportunities to service_role;
grant select, insert, update, delete on table public.cardflip_trades to service_role;
grant select, insert, update, delete on table public.cardflip_execution_logs to service_role;
grant select, insert, update, delete on table public.cardflip_opportunity_reject_logs to service_role;
