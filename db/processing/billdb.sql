SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0;
SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0;
SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='TRADITIONAL';

CREATE SCHEMA IF NOT EXISTS `skyline` DEFAULT CHARACTER SET latin1 ;
USE `skyline` ;

-- -----------------------------------------------------
-- Table `skyline`.`customer`
-- -----------------------------------------------------
CREATE  TABLE IF NOT EXISTS `skyline`.`customer` (
  `id` INT(11) NOT NULL AUTO_INCREMENT ,
  `name` VARCHAR(45) NOT NULL ,
  `account` VARCHAR(45) NOT NULL ,
  `discountrate` DECIMAL(3,2) NOT NULL ,
  PRIMARY KEY (`id`) )
ENGINE = InnoDB
AUTO_INCREMENT = 21
DEFAULT CHARACTER SET = utf8;


-- -----------------------------------------------------
-- Table `skyline`.`payment`
-- -----------------------------------------------------
CREATE  TABLE IF NOT EXISTS `skyline`.`payment` (
  `id` INT(11) NOT NULL AUTO_INCREMENT ,
  `date` DATE NOT NULL ,
  `description` VARCHAR(45) CHARACTER SET 'utf8' NULL DEFAULT NULL ,
  `credit` DECIMAL(6,2) NULL DEFAULT NULL ,
  `customer_id` INT(11) NOT NULL ,
  PRIMARY KEY (`id`) ,
  INDEX `fk_payment_customer` (`customer_id` ASC) ,
  CONSTRAINT `fk_payment_customer`
    FOREIGN KEY (`customer_id` )
    REFERENCES `skyline`.`customer` (`id` )
    ON DELETE NO ACTION
    ON UPDATE NO ACTION)
ENGINE = InnoDB
AUTO_INCREMENT = 40
DEFAULT CHARACTER SET = utf8
COLLATE = utf8_unicode_ci;


-- -----------------------------------------------------
-- Table `skyline`.`rebill`
-- -----------------------------------------------------
CREATE  TABLE IF NOT EXISTS `skyline`.`rebill` (
  `id` INT(11) NOT NULL AUTO_INCREMENT ,
  `sequence` INT(11) NOT NULL ,
  `customer_id` INT(11) NOT NULL ,
  `issued` TINYINT(1) NULL DEFAULT NULL ,
  PRIMARY KEY (`id`) ,
  UNIQUE INDEX `unique_constraint` (`customer_id` ASC, `sequence` ASC) ,
  INDEX `fk_rebill_customer` (`customer_id` ASC) ,
  CONSTRAINT `fk_rebill_customer`
    FOREIGN KEY (`customer_id` )
    REFERENCES `skyline`.`customer` (`id` )
    ON DELETE NO ACTION
    ON UPDATE NO ACTION)
ENGINE = InnoDB
AUTO_INCREMENT = 209
DEFAULT CHARACTER SET = utf8;


-- -----------------------------------------------------
-- Table `skyline`.`utilbill`
-- -----------------------------------------------------
CREATE  TABLE IF NOT EXISTS `skyline`.`utilbill` (
  `id` INT(11) NOT NULL AUTO_INCREMENT ,
  `customer_id` INT(11) NULL DEFAULT NULL ,
  `rebill_id` INT(11) NULL DEFAULT NULL ,
  `period_start` DATE NOT NULL ,
  `period_end` DATE NOT NULL ,
  `estimated` TINYINT(1) NULL DEFAULT NULL ,
  `processed` TINYINT(1) NULL DEFAULT NULL ,
  `received` TINYINT(1) NULL DEFAULT NULL ,
  PRIMARY KEY (`id`) ,
  INDEX `fk_utilbill_customer` (`customer_id` ASC) ,
  INDEX `fk_utilbill_rebill` (`rebill_id` ASC) ,
  CONSTRAINT `fk_utilbill_customer`
    FOREIGN KEY (`customer_id` )
    REFERENCES `skyline`.`customer` (`id` )
    ON DELETE NO ACTION
    ON UPDATE NO ACTION,
  CONSTRAINT `fk_utilbill_rebill`
    FOREIGN KEY (`rebill_id` )
    REFERENCES `skyline`.`rebill` (`id` )
    ON DELETE NO ACTION
    ON UPDATE NO ACTION)
ENGINE = InnoDB
AUTO_INCREMENT = 251
DEFAULT CHARACTER SET = utf8;


-- -----------------------------------------------------
-- Placeholder table for view `skyline`.`status_days_since`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `skyline`.`status_days_since` (`account` INT, `name` INT, `dayssince` INT);

-- -----------------------------------------------------
-- Placeholder table for view `skyline`.`status_unbilled`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `skyline`.`status_unbilled` (`account` INT, `name` INT);

-- -----------------------------------------------------
-- View `skyline`.`status_days_since`
-- -----------------------------------------------------
DROP TABLE IF EXISTS `skyline`.`status_days_since`;
USE `skyline`;
CREATE  OR REPLACE ALGORITHM=UNDEFINED DEFINER=`root`@`10.0.0.%` SQL SECURITY INVOKER VIEW `skyline`.`status_days_since` AS select `c`.`account` AS `account`,`c`.`name` AS `name`,(to_days(curdate()) - to_days(max(`u`.`period_end`))) AS `dayssince` from ((`skyline`.`utilbill` `u` left join `skyline`.`rebill` `r` on((`u`.`rebill_id` = `r`.`id`))) join `skyline`.`customer` `c`) where ((`u`.`customer_id` = `c`.`id`) and (`u`.`rebill_id` is not null)) group by `c`.`name` order by `c`.`account`;

-- -----------------------------------------------------
-- View `skyline`.`status_unbilled`
-- -----------------------------------------------------
DROP TABLE IF EXISTS `skyline`.`status_unbilled`;
USE `skyline`;
CREATE  OR REPLACE ALGORITHM=UNDEFINED DEFINER=`root`@`10.0.0.%` SQL SECURITY INVOKER VIEW `skyline`.`status_unbilled` AS select `c`.`account` AS `account`,`c`.`name` AS `name` from (`skyline`.`customer` `c` left join `skyline`.`utilbill` `ub` on((`ub`.`customer_id` = `c`.`id`))) where isnull(`ub`.`customer_id`);


SET SQL_MODE=@OLD_SQL_MODE;
SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS;
SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS;

