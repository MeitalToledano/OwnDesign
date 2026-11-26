-- AI furniture-layout suggestions for one room. A row records each request (what was asked, the outcome)
-- and doubles as the daily cap: reserve_layout_suggestion counts a user's rows of the last 24 hours under a
-- per-user lock and inserts the new one before the paid call, so parallel requests cannot pass the cap.
create table public.layout_suggestions (
  id bigint generated always as identity primary key,
  project_id uuid not null references public.projects on delete cascade,
  user_id uuid not null references auth.users on delete cascade,
  room_id text not null check (char_length(room_id) between 1 and 40),
  request jsonb not null,
  status text not null default 'pending' check (status in ('pending', 'done', 'failed')),
  result jsonb,
  created_at timestamptz not null default now()
);
create index layout_suggestions_user_idx on public.layout_suggestions (user_id, created_at);
create index layout_suggestions_project_idx on public.layout_suggestions (project_id);

alter table public.layout_suggestions enable row level security;
revoke all on public.layout_suggestions from anon, authenticated;
grant select on public.layout_suggestions to authenticated;
grant select, insert, update on public.layout_suggestions to service_role;
revoke all on sequence public.layout_suggestions_id_seq from anon, authenticated;
grant usage on sequence public.layout_suggestions_id_seq to service_role;

-- A suggestion is private to the user who asked for it, like a consultant conversation.
create policy layout_suggestions_select_own on public.layout_suggestions
  for select to authenticated
  using (user_id = (select auth.uid()) and project_id in (select id from public.projects));

create function public.reserve_layout_suggestion(p_project uuid, p_user uuid, p_room text, p_request jsonb, p_cap int)
returns bigint language plpgsql security definer set search_path = '' as $$
declare used int; new_id bigint;
begin
  -- Its own lock key, so a layout request never waits on the same user's consultant message.
  perform pg_advisory_xact_lock(hashtextextended('layout:' || p_user::text, 0));
  select count(*) into used from public.layout_suggestions
   where user_id = p_user and created_at > now() - interval '1 day';
  if used >= p_cap then
    raise exception 'daily layout cap reached' using errcode = 'P0001';
  end if;
  insert into public.layout_suggestions (project_id, user_id, room_id, request)
    values (p_project, p_user, p_room, p_request) returning id into new_id;
  return new_id;
end $$;

revoke all on function public.reserve_layout_suggestion(uuid, uuid, text, jsonb, int) from public, anon, authenticated;
grant execute on function public.reserve_layout_suggestion(uuid, uuid, text, jsonb, int) to service_role;
