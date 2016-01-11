DROP TABLE IF EXISTS `status_days_since`;
CREATE  OR REPLACE ALGORITHM=UNDEFINED DEFINER=`root`@`10.0.0.%` SQL SECURITY INVOKER VIEW `status_days_since` AS 
(select `c`.`id`, `c`.`account` AS `account`,
`c`.`name` AS `name`,
cast((to_days(curdate()) - to_days(max(`u`.`period_end`))) as SIGNED INTEGER) AS `dayssince` 
from ((`utilbill` `u` left join `rebill` `r` on ((`u`.`rebill_id` = `r`.`id`))) join `customer` `c`) 
where ((`u`.`customer_id` = `c`.`id`) )
group by `c`.`account` 
order by `c`.`account`)
union
(select `c`.`id`, `c`.`account` AS `account`,
`c`.`name` AS `name`,
null AS `dayssince` 
from (`customer` `c` left join `utilbill` `u` on `c`.`id` = `u`.`customer_id`)
where `u`.`id` is null
group by c.`account` 
order by c.`account`);

ALTER TABLE `customer` ADD UNIQUE(`account`);
