'''Rename "rebill" to "reebill".'''
from MySQLdb import Connection

con = Connection('localhost', 'dev', 'dev', 'skyline_dev')
cur = con.cursor()

cur.execute('''
ALTER ALGORITHM=UNDEFINED DEFINER=`root`@`10.0.0.%` SQL SECURITY INVOKER VIEW `status_days_since` AS (select `c`.`id` AS `id`,`c`.`account` AS `account`,`c`.`name` AS `name`,cast((to_days(curdate()) - to_days(max(`u`.`period_end`))) as signed) AS `dayssince` from ((`utilbill_version` `u` left join `reebill` `r` on((`u`.`reebill_id` = `r`.`id`))) join `customer` `c`) where (`u`.`customer_id` = `c`.`id`) group by `c`.`account` order by `c`.`account`) union (select `c`.`id` AS `id`,`c`.`account` AS `account`,`c`.`name` AS `name`,NULL AS `dayssince` from (`customer` `c` left join `utilbill_version` `u` on((`c`.`id` = `u`.`customer_id`))) where isnull(`u`.`id`) group by `c`.`account` order by `c`.`account`);
''')
