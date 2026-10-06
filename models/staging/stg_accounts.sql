-- one row per deposit account, with the three keys that answer three different questions:
--   holder_key          who the sweep engine allocates for (the account holder)
--   insured_owner_key   who the FDIC insures (12 CFR 330: a sole proprietorship is its owner)
--   relationship_key    the founder behind the entities
--   investor_key        the lead investor whose portfolio may move its cash on the same day
select
    a.account_id,
    a.account_type,
    a.opened_at,
    a.closed_at,
    a.depositor_id,
    d.entity_type,
    case when a.person_id is not null then 'P' || a.person_id
         else 'D' || a.depositor_id end                                    as holder_key,
    case when a.person_id is not null then 'P' || a.person_id
         when d.entity_type = 'sole_prop' then 'P' || d.owner_person_id
         else 'E' || a.depositor_id end                                    as insured_owner_key,
    case when a.person_id is not null or d.entity_type = 'sole_prop' then 'single'
         else 'business' end                                               as ownership_category,
    'R' || coalesce(a.person_id, d.owner_person_id)                        as relationship_key,
    coalesce('V' || d.lead_investor_id, 'E' || a.depositor_id, 'P' || a.person_id) as investor_key
from {{ source('raw', 'accounts') }} a
left join {{ source('raw', 'depositors') }} d on d.depositor_id = a.depositor_id
