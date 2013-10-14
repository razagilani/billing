use skyline_dev;

-- create junction table for utilbill/reebill relationship
-- note the cascade: rows from this table automatically get deleted when either
-- the utilbill or the reebill is deleted
create table utilbill_reebill (
    utilbill_id int(11) not null,
    reebill_id int(11) not null,

    -- NOTE utilbill_id has "on delete restrict" so that attempts to delete a
    -- utility bill that has a reebill will fail, but reebill_id has "on delete
    -- cascade" so the utilbill_reebill row corresponding to a reebill
    -- automatically disappears when the reebill is deleted.
    foreign key (utilbill_id) references utilbill (id) on delete restrict,
    foreign key (reebill_id) references rebill (id) on delete cascade,

    primary key (utilbill_id, reebill_id)
);

-- copy reebill/utilbill associations from utilbill.reebill_id into the new table
insert into utilbill_reebill (utilbill_id, reebill_id) select id, rebill_id from utilbill where rebill_id is not null;

-- drop constraints preventing removal of the reebill_id column, then remove it
alter table utilbill drop foreign key fk_utilbill_rebill;
alter table utilbill drop key fk_utilbill_rebill;
alter table utilbill drop column rebill_id;

