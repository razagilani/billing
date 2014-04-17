-- Change MySQL column types to float so SQLAlchemy does not automatically turn
-- them into Decimals and mess up arithmetic everywhere.

alter table customer change column discountrate discountrate float;
alter table customer change column latechargerate latechargerate float;
alter table utilbill change column total_charges total_charges float;
alter table payment change column credit credit float;
