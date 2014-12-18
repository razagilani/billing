import logging
from billing.core.model.model import Utility, UtilityAccount, \
    UtilBill, RateClass


log = logging.getLogger(__name__)


def account_bills_2_rate_class(session, account_str, rate_class):
    utilbills = session.query(UtilBill).join(
        UtilityAccount, UtilityAccount.id ==
        UtilBill.utility_account_id).filter(
        UtilityAccount.account == account_str
    )
    for bill in utilbills:
       bill.rate_class = rate_class


def clean_up_rate_class_data(session):
    # Utilities
    PIEDMONT = session.query(Utility).filter(Utility.name == 'piedmont').one()
    WGES = session.query(Utility).filter(
        Utility.name == 'washington gas').one()
    PEPCO = session.query(Utility).filter(Utility.name == 'pepco').one()
    BGE = session.query(Utility).filter(Utility.name == 'bge').one()
    SEMPERA = session.query(Utility).filter(Utility.name == 'Sempra Energy').one()
    PGE = session.query(Utility).filter(Utility.name == 'PG&E').one()
    PECO = session.query(Utility).filter(Utility.name == 'peco').one()
    MAUI = session.query(Utility).filter(
        Utility.name == 'Maui Electric Company').one()
    DOMINION = session.query(Utility).filter(Utility.name == 'dominion').one()

    print PIEDMONT, WGES, PEPCO, PECO, DOMINION

    # RATE CLASSES
    # PIEDMONT
    ONEZEROONERESIDENTIAL_MOORE_NC_Moore = RateClass(
        "101 RESIDENTIAL SERVICE RATE_NC_Moore", PIEDMONT
    )
    session.add(ONEZEROONERESIDENTIAL_MOORE_NC_Moore)

    # WGES
    COMMERCIAL_HEAT_COOL_DC = RateClass("COMMERCIAL HEAT/COOL_DC_DC", WGES)
    session.add(COMMERCIAL_HEAT_COOL_DC)

    NONRESIDENTIAL_NONHEAT_Level_1 = RateClass(
        "NONRESIDENTIAL NONHEAT_Level 1_DC_DC", WGES
    )
    session.add(NONRESIDENTIAL_NONHEAT_Level_1)
    NONRESIDENTIAL_NONHEAT_Level_2 = RateClass(
        "NONRESIDENTIAL NONHEAT_Level 2_DC_DC", WGES
    )
    session.add(NONRESIDENTIAL_NONHEAT_Level_2)
    NONRESIDENTIAL_HEAT_Level_1 = RateClass(
        "NONRESIDENTIAL HEAT_Level 1_DC_DC", WGES
    )
    session.add(NONRESIDENTIAL_HEAT_Level_1)
    NONRESIDENTIAL_HEAT_Level_2 = RateClass(
        "NONRESIDENTIAL HEAT_Level 2_DC_DC", WGES
    )
    session.add(NONRESIDENTIAL_HEAT_Level_2)
    NONRESIDENTIAL_HEAT = RateClass(
        "NONRESIDENTIAL HEAT_DC_DC", WGES
    )
    session.add(NONRESIDENTIAL_HEAT_Level_2)
    NONRESIDENTIAL_NONHEAT_NEW = RateClass(
        "Commercial and Industrial Non-heating/Non-cooling Delivery "
        "Service_DC_DC", WGES
    )
    session.add(NONRESIDENTIAL_NONHEAT_NEW)
    NONRESIDENTIAL_HEAT_NEW = RateClass(
        "Commercial and Industrial Heating Delivery "
        "Service_DC_DC", WGES
    )
    session.add(NONRESIDENTIAL_HEAT_NEW)
    NONRESIDENTIAL_NONHEAT = RateClass(
        "NONRESIDENTIAL NONHEAT_DC_DC", WGES
    )
    session.add(NONRESIDENTIAL_NONHEAT)

    RESIDENTIAL_HEAT_PRINCE_GEORGE = RateClass(
        "RESIDENTIAL HEAT/COOL_MD_Prince George's", WGES)
    session.add(RESIDENTIAL_HEAT_PRINCE_GEORGE)

    APT_HEAT_NEW = RateClass(
        'Group Metered Apartments Heating Delivery Service_DC_DC', WGES
    )
    session.add(APT_HEAT_NEW)
    APT_HEAT_NEW_MONTGOMERY = RateClass(
        'Group Metered Apartments Heating Delivery Service_MD_Montgomery', WGES
    )
    session.add(APT_HEAT_NEW_MONTGOMERY)
    APT_NONHEAT_NEW_PRINCE_GEORGE = RateClass(
        "Group Metered Apartments Non-heating/Non-cooling Delivery Service"
        "_MD_Prince George's", WGES
    )
    session.add(APT_NONHEAT_NEW_PRINCE_GEORGE)

    APT_NONHEAT_PRINCE_GEORGE = RateClass(
        "GROUP METER APT NONHEAT_MD_Prince George's", WGES
    )
    session.add(APT_NONHEAT_PRINCE_GEORGE)
    APT_NONHEAT_MONTGOMERY = RateClass(
        "GROUP METER APT NONHEAT_MD_Montgomery", WGES
    )
    session.add(APT_NONHEAT_MONTGOMERY)
    APT_HEAT_PRINCE_GEORGE = RateClass(
        "GROUP METER APT HEAT/COOL_MD_Prince George's", WGES
    )
    session.add(APT_HEAT_PRINCE_GEORGE)

    DELIVERY_INTERRUPT = RateClass(
        "DELIVERY/INTERRUPT_DC_DC", WGES
    )
    session.add(DELIVERY_INTERRUPT)
    DELIVERY_INTERRUPT_PRINCE_GEORGE = RateClass(
        "DELIVERY/INTERRUPT_MD_Prince George's", WGES
    )
    session.add(DELIVERY_INTERRUPT_PRINCE_GEORGE)
    DELIVERY_INTERRUPT_NEW = RateClass(
        "Interruptible Heating Delivery Service_DC_DC", WGES
    )
    session.add(DELIVERY_INTERRUPT_NEW)


    # DOMINION
    NON_RESIDENTIAL_GS_1 = RateClass(
        "Non-Residential Service (Schedule GS-1)_VA_Alexandria", DOMINION
    )
    session.add(NON_RESIDENTIAL_GS_1)


    # BGE
    GENERAL_SERVICE_SCHEDULE_C_ANNE_ARUNDEL = RateClass(
        "General Service Schedule C_MD_Anne Arundel", BGE
    )
    session.add(GENERAL_SERVICE_SCHEDULE_C_ANNE_ARUNDEL)
    GENERAL_SERVICE_SCHEDULE_C_BALTIMORE = RateClass(
        "General Service Schedule C_MD_Baltimore", BGE
    )
    session.add(GENERAL_SERVICE_SCHEDULE_C_BALTIMORE)
    TOU_Schedule_GL = RateClass(
        "Large General Service - TOU Schedule GL - POLR Type II_MD_Prince "
        "George's", BGE
    )
    session.add(TOU_Schedule_GL)

    # PEPCO
    NON_RESIDENTIAL_GT = RateClass(
        "Non-Residential-GT_DC_DC", PEPCO
    )
    session.add(NON_RESIDENTIAL_GT)
    NON_RESIDENTIAL_GS_D = RateClass(
        "Non-Residential-GS D_DC_DC", PEPCO
    )
    session.add(NON_RESIDENTIAL_GS_D)
    NON_RESIDENTIAL_GS_ND = RateClass(
        "Non-Residential-GS ND_DC_DC", PEPCO
    )
    session.add(NON_RESIDENTIAL_GS_ND)
    RESIDENTIAL_R_DC = RateClass(
        "Residential-R_DC_DC", PEPCO
    )
    session.add(RESIDENTIAL_R_DC)

    # PECO
    ELECTRIC_0_100_PHILADELPHIA = RateClass(
        "Electric Commercial Service 0-100kW_PA_Philadelphia", PECO
    )
    session.add(ELECTRIC_0_100_PHILADELPHIA)
    GAS_COMMERCIAL_SERVICE_CHESTER = RateClass(
        "Gas Commercial Service_PA_Chester", PECO
    )
    session.add(GAS_COMMERCIAL_SERVICE_CHESTER)

    session.flush()

    account_bills_2_rate_class(session, '10001', COMMERCIAL_HEAT_COOL_DC)
    account_bills_2_rate_class(session, '10002', ONEZEROONERESIDENTIAL_MOORE_NC_Moore)
    account_bills_2_rate_class(session, '10003', NONRESIDENTIAL_NONHEAT_NEW)
    account_bills_2_rate_class(session, '10004', GAS_COMMERCIAL_SERVICE_CHESTER)
    account_bills_2_rate_class(session, '10005', NONRESIDENTIAL_HEAT_Level_1)
    account_bills_2_rate_class(session, '10006', NONRESIDENTIAL_NONHEAT_NEW)
    account_bills_2_rate_class(session, '10007', NONRESIDENTIAL_NONHEAT_NEW)
    # No bills for 10008
    account_bills_2_rate_class(session, '10009', RESIDENTIAL_R_DC)
    account_bills_2_rate_class(session, '10010', NONRESIDENTIAL_NONHEAT_NEW)
    account_bills_2_rate_class(session, '10011', NONRESIDENTIAL_HEAT_Level_2)
    account_bills_2_rate_class(session, '10012', NONRESIDENTIAL_HEAT)
    account_bills_2_rate_class(session, '10013', NONRESIDENTIAL_HEAT)
    account_bills_2_rate_class(session, '10014', NONRESIDENTIAL_HEAT_NEW)
    # Account 10015 missing
    account_bills_2_rate_class(session, '10016', NONRESIDENTIAL_HEAT)
    account_bills_2_rate_class(session, '10017', TOU_Schedule_GL)


if __name__ == '__main__':
    # for testing in development environment
    from billing import init_config, init_model, init_logging

    init_config()
    init_model()
    init_logging()
    from billing.core.model import Session

    session = Session()
    clean_up_rate_class_data(session)
    session.commit()
