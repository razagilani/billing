start transaction;

alter table utilbill add date_recieved datetime
alter table utilbill rename received state integer;
update utilbill set state = 0;
update utilbill set state = 1 where estimated = 1;
alter table utilbill drop column estimated;
update utilbill set state = 4 where customer_id = 5;

DROP TABLE IF EXISTS `skyline_stage`.`status_days_since`;
USE `skyline_stage`;
CREATE  OR REPLACE ALGORITHM=UNDEFINED DEFINER=`root`@`10.0.0.%` SQL SECURITY INVOKER VIEW `status_days_since` AS 
(select `c`.`id`, `c`.`account` AS `account`,
`c`.`name` AS `name`,
cast((to_days(curdate()) - to_days(max(`u`.`period_end`))) as char(32)) AS `dayssince` 
from ((`utilbill` `u` left join `rebill` `r` on ((`u`.`rebill_id` = `r`.`id`))) join `customer` `c`) 
where ((`u`.`customer_id` = `c`.`id`) )
group by `c`.`account` 
order by `c`.`account`)
union
(select `c`.`id`, `c`.`account` AS `account`,
`c`.`name` AS `name`,
'N/A' AS `dayssince` 
from (`customer` `c` left join `utilbill` `u` on `c`.`id` = `u`.`customer_id`)
where `u`.`id` is null
group by c.`account` 
order by c.`account`);

