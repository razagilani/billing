/* makes all bills "issued" in mysql whose successor is issued */
drop table t;

create table t as select customer_id, sequence from rebill where issued = 1;
create table u as select customer_id, sequence from rebill where issued = 1;
update rebill set issued = 1 where rebill.id in (select id from u, t where u.customer_id = t.customer_id and u.sequence + 1 = t.sequence);

drop table t;
