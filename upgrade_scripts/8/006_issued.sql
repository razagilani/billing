/* makes all bills "issued" in mysql where any bill for the same account but with higher sequence is issued */
create temporary table t select * from rebill;
create temporary table u select * from rebill;
update rebill set issued = 1 where id in (select u.id from t, u where t.customer_id = u.customer_id and t.issued = 1 and t.sequence > u.sequence);
