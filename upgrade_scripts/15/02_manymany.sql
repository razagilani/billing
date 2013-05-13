use skyline_dev;

-- create junction table for utilbill/reebill relationship
create table utilbill_reebill (
    utilbill_id int(11) not null,
    reebill_id int(11) not null,
    foreign key (utilbill_id) references utilbill (id),
    foreign key (reebill_id) references rebill (id),
    primary key (utilbill_id, reebill_id)
);
-- copy data from utilbill.rebill_id into the new table
insert into utilbill_reebill (utilbill_id, reebill_id) select id, rebill_id from utilbill where rebill_id is not null;

-- drop constraints preventing removal of the rebill_id column, then remove it
alter table utilbill drop foreign key fk_utilbill_rebill;
alter table utilbill drop key fk_utilbill_rebill;
alter table utilbill drop column rebill_id;
