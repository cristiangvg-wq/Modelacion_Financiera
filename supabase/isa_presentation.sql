-- ISA Investment Room: almacenamiento compartido y lectura protegida por token.
-- Ejecutar una sola vez en Supabase > SQL Editor.
create extension if not exists pgcrypto with schema extensions;

create table if not exists public.isa_valuation_snapshots (
    ticker text primary key check (ticker = 'ISA'),
    company_name text not null,
    model_version text not null,
    payload jsonb not null,
    published_at timestamptz not null default now()
);

alter table public.isa_valuation_snapshots enable row level security;
revoke all on table public.isa_valuation_snapshots from anon, authenticated;
grant all on table public.isa_valuation_snapshots to service_role;

create table if not exists public.isa_presentation_access (
    singleton boolean primary key default true check (singleton),
    token_sha256 text not null
);
alter table public.isa_presentation_access enable row level security;
revoke all on table public.isa_presentation_access from anon, authenticated;
grant all on table public.isa_presentation_access to service_role;

-- Reemplaza el valor de ejemplo por SHA-256 del token aleatorio que generarás.
-- No guardes el token original en GitHub ni en SQL compartido.
insert into public.isa_presentation_access (singleton, token_sha256)
values (true, 'REEMPLAZAR_POR_SHA256_HEX')
on conflict (singleton) do update
set token_sha256 = excluded.token_sha256;

create or replace function public.get_isa_latest_snapshot(p_token text)
returns jsonb
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
    expected_hash text;
    supplied_hash text;
    snapshot jsonb;
begin
    select token_sha256 into expected_hash
    from public.isa_presentation_access
    where singleton = true;

    supplied_hash := encode(extensions.digest(convert_to(coalesce(p_token, ''), 'UTF8'), 'sha256'), 'hex');

    if expected_hash is null or supplied_hash <> expected_hash then
        raise exception 'Unauthorized' using errcode = '42501';
    end if;

    select jsonb_build_object(
        'ticker', ticker,
        'company_name', company_name,
        'model_version', model_version,
        'published_at', published_at,
        'payload', payload
    ) into snapshot
    from public.isa_valuation_snapshots
    where ticker = 'ISA';

    return snapshot;
end;
$$;

revoke all on function public.get_isa_latest_snapshot(text) from public, authenticated;
grant execute on function public.get_isa_latest_snapshot(text) to anon;
