-- Bronze: the landed source made queryable, and nothing else. No
-- renaming, no casting, no filtering - so every silver column can be
-- traced back to exactly what arrived, byte for byte.
select * from {{ ry_raw('enrolment') }}
