SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0;
SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0;
SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='TRADITIONAL';

CREATE SCHEMA IF NOT EXISTS `skyline` DEFAULT CHARACTER SET utf8 COLLATE utf8_general_ci ;
SHOW WARNINGS;
USE `skyline` ;

-- -----------------------------------------------------
-- Table `skyline`.`customer`
-- -----------------------------------------------------
CREATE  TABLE IF NOT EXISTS `skyline`.`customer` (
  `id` INT NOT NULL AUTO_INCREMENT ,
  `name` VARCHAR(45) NOT NULL ,
  `account` VARCHAR(45) NOT NULL ,
  `discountrate` DECIMAL(3,2) NOT NULL ,
  PRIMARY KEY (`id`) )
ENGINE = InnoDB;

SHOW WARNINGS;

-- -----------------------------------------------------
-- Table `skyline`.`rebill`
-- -----------------------------------------------------
CREATE  TABLE IF NOT EXISTS `skyline`.`rebill` (
  `id` INT NOT NULL AUTO_INCREMENT ,
  `uri` VARCHAR(1024) NOT NULL ,
  `sequence` INT NOT NULL ,
  `customer_id` INT NOT NULL ,
  PRIMARY KEY (`id`) ,
  INDEX `fk_rebill_customer` (`customer_id` ASC) ,
  CONSTRAINT `fk_rebill_customer`
    FOREIGN KEY (`customer_id` )
    REFERENCES `skyline`.`customer` (`id` )
    ON DELETE NO ACTION
    ON UPDATE NO ACTION)
ENGINE = InnoDB;

SHOW WARNINGS;

-- -----------------------------------------------------
-- Table `skyline`.`ledger`
-- -----------------------------------------------------
CREATE  TABLE IF NOT EXISTS `skyline`.`ledger` (
  `id` INT NOT NULL AUTO_INCREMENT ,
  `date` DATE NOT NULL ,
  `description` VARCHAR(45) NULL ,
  `debit` DECIMAL(6,2) NULL ,
  `credit` DECIMAL(6,2) NULL ,
  `customer_id` INT NOT NULL ,
  `rebill_id` INT NULL ,
  PRIMARY KEY (`id`, `customer_id`) ,
  INDEX `fk_ledger_customer` (`customer_id` ASC) ,
  INDEX `fk_ledger_bill` (`rebill_id` ASC) ,
  CONSTRAINT `fk_ledger_customer`
    FOREIGN KEY (`customer_id` )
    REFERENCES `skyline`.`customer` (`id` )
    ON DELETE NO ACTION
    ON UPDATE NO ACTION,
  CONSTRAINT `fk_ledger_bill`
    FOREIGN KEY (`rebill_id` )
    REFERENCES `skyline`.`rebill` (`id` )
    ON DELETE NO ACTION
    ON UPDATE NO ACTION)
ENGINE = InnoDB;

SHOW WARNINGS;

-- -----------------------------------------------------
-- Table `skyline`.`utility`
-- -----------------------------------------------------
CREATE  TABLE IF NOT EXISTS `skyline`.`utility` (
  `id` INT NOT NULL ,
  `identifier` VARCHAR(45) NOT NULL ,
  `name` VARCHAR(45) NOT NULL ,
  PRIMARY KEY (`id`) )
ENGINE = InnoDB;

SHOW WARNINGS;

-- -----------------------------------------------------
-- Table `skyline`.`utilbill`
-- -----------------------------------------------------
CREATE  TABLE IF NOT EXISTS `skyline`.`utilbill` (
  `id` INT NOT NULL AUTO_INCREMENT ,
  `customer_id` INT NULL ,
  `rebill_id` INT NULL ,
  `uri` VARCHAR(1024) NULL ,
  `period_start` DATE NOT NULL ,
  `period_end` DATE NOT NULL ,
  `estimated` TINYINT(1)  NULL ,
  `processed` TINYINT(1)  NULL ,
  `received` TINYINT(1)  NULL ,
  `utility_id` INT NULL ,
  PRIMARY KEY (`id`) ,
  INDEX `fk_utilbill_customer` (`customer_id` ASC) ,
  INDEX `fk_utilbill_rebill` (`rebill_id` ASC) ,
  INDEX `fk_utilbill_utility` () ,
  CONSTRAINT `fk_utilbill_customer`
    FOREIGN KEY (`customer_id` )
    REFERENCES `skyline`.`customer` (`id` )
    ON DELETE NO ACTION
    ON UPDATE NO ACTION,
  CONSTRAINT `fk_utilbill_rebill`
    FOREIGN KEY (`rebill_id` )
    REFERENCES `skyline`.`rebill` (`id` )
    ON DELETE NO ACTION
    ON UPDATE NO ACTION,
  CONSTRAINT `fk_utilbill_utility`
    FOREIGN KEY ()
    REFERENCES `skyline`.`utility` ()
    ON DELETE NO ACTION
    ON UPDATE NO ACTION)
ENGINE = InnoDB;

SHOW WARNINGS;


SET SQL_MODE=@OLD_SQL_MODE;
SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS;
SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS;
