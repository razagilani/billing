use skyline_dev

alter table utilbill add total_charges decimal(14,4);
update utilbill set total_charges = 0.0000 where total_charges is null;
