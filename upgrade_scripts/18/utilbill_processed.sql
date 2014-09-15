-- Convert utilbill.processed into a usable column.

update utilbill set processed = 1 where processed = null;
alter table utilbill change column processed processed boolean not null;
-- apparently "boolean" is an alias for tinyint(1)
