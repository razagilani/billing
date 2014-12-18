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
    COMMERCIAL_HEAT_COOL_DC_Level_1 = RateClass(
        "COMMERCIAL HEAT/COOL_Level 1_DC_DC", WGES)
    session.add(COMMERCIAL_HEAT_COOL_DC_Level_1)
    COMMERCIAL_HEAT_COOL_DC_Level_2 = RateClass(
        "COMMERCIAL HEAT/COOL_Level 2_DC_DC", WGES)
    session.add(COMMERCIAL_HEAT_COOL_DC_Level_2)

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
    APT_HEAT_NEW_PRINCE_GEORGE = RateClass(
        "Group Metered Apartments Heating Delivery Service_MD_Prince George's", WGES
    )
    session.add(APT_HEAT_NEW_PRINCE_GEORGE)
    APT_NONHEAT_NEW_PRINCE_GEORGE = RateClass(
        "Group Metered Apartments Non-heating/Non-cooling Delivery Service"
        "_MD_Prince George's", WGES
    )
    session.add(APT_NONHEAT_NEW_PRINCE_GEORGE)
    APT_NONHEAT_NEW = RateClass(
        "Group Metered Apartments Non-heating/Non-cooling Delivery Service"
        "_DC_DC", WGES
    )
    session.add(APT_NONHEAT_NEW)
    APT_NONHEAT_NEW_ARLINGTON = RateClass(
        "Group Metered Apartments Non-heating/Non-cooling Delivery Service"
        "_VA_Arlington", WGES
    )
    session.add(APT_NONHEAT_NEW_ARLINGTON)

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
    APT_HEAT_MONTGOMERY = RateClass(
        "GROUP METER APT HEAT/COOL_MD_Montgomery", WGES
    )
    session.add(APT_HEAT_MONTGOMERY)

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
    account_bills_2_rate_class(session, '10018', NON_RESIDENTIAL_GS_1)
    account_bills_2_rate_class(session, '10019', NONRESIDENTIAL_NONHEAT)
    # Account 10020 missing
    account_bills_2_rate_class(session, '10021', NONRESIDENTIAL_NONHEAT_Level_2)
    account_bills_2_rate_class(session, '10022', NONRESIDENTIAL_NONHEAT_Level_1)
    account_bills_2_rate_class(session, '10023', NONRESIDENTIAL_NONHEAT_Level_2)
    account_bills_2_rate_class(session, '10024', NONRESIDENTIAL_NONHEAT_Level_2)
    account_bills_2_rate_class(session, '10025', NONRESIDENTIAL_HEAT)
    account_bills_2_rate_class(session, '10026', APT_NONHEAT_NEW_ARLINGTON)
    account_bills_2_rate_class(session, '10027', APT_NONHEAT_NEW)
    account_bills_2_rate_class(session, '10028', APT_NONHEAT_NEW)
    # TODO: CA
    account_bills_2_rate_class(session, '10032', DELIVERY_INTERRUPT)
    account_bills_2_rate_class(session, '10033',
                               GENERAL_SERVICE_SCHEDULE_C_ANNE_ARUNDEL)
    account_bills_2_rate_class(session, '10034',
                               GENERAL_SERVICE_SCHEDULE_C_ANNE_ARUNDEL)
    account_bills_2_rate_class(session, '10035',
                               GENERAL_SERVICE_SCHEDULE_C_ANNE_ARUNDEL)
    account_bills_2_rate_class(session, '10036',
                               GENERAL_SERVICE_SCHEDULE_C_ANNE_ARUNDEL)
    account_bills_2_rate_class(session, '10037',
                               GENERAL_SERVICE_SCHEDULE_C_ANNE_ARUNDEL)
    account_bills_2_rate_class(session, '10038',
                               GENERAL_SERVICE_SCHEDULE_C_ANNE_ARUNDEL)
    account_bills_2_rate_class(session, '10039',
                               GENERAL_SERVICE_SCHEDULE_C_ANNE_ARUNDEL)
    account_bills_2_rate_class(session, '10040',
                               GENERAL_SERVICE_SCHEDULE_C_ANNE_ARUNDEL)
    account_bills_2_rate_class(session, '10041',
                               GENERAL_SERVICE_SCHEDULE_C_ANNE_ARUNDEL)
    account_bills_2_rate_class(session, '10042',
                               GENERAL_SERVICE_SCHEDULE_C_ANNE_ARUNDEL)
    account_bills_2_rate_class(session, '10043',
                               GENERAL_SERVICE_SCHEDULE_C_ANNE_ARUNDEL)
    account_bills_2_rate_class(session, '10045', NON_RESIDENTIAL_GT)
    # TODO: CONOCO PHilips Individual contract
    # Account 10047, 10048 missing
    # PECO Individual contract
    account_bills_2_rate_class(session, '10050', APT_HEAT_NEW_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10051', APT_HEAT_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10052', APT_HEAT_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10053', APT_HEAT_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10054', APT_HEAT_NEW_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10055', APT_HEAT_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10056', APT_HEAT_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10057', APT_HEAT_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10058', NONRESIDENTIAL_HEAT_Level_2)
    account_bills_2_rate_class(session, '10059', NONRESIDENTIAL_HEAT_Level_2)
    # TODO: PG&E
    account_bills_2_rate_class(session, '10061', DELIVERY_INTERRUPT_NEW)
    account_bills_2_rate_class(session, '10062', NONRESIDENTIAL_HEAT)
    account_bills_2_rate_class(session, '10063', GENERAL_SERVICE_SCHEDULE_C_ANNE_ARUNDEL)
    # TODO: Skipping 10064, 10065
    account_bills_2_rate_class(session, '10066', NONRESIDENTIAL_NONHEAT_NEW)
    account_bills_2_rate_class(session, '10067', NONRESIDENTIAL_HEAT)
    account_bills_2_rate_class(session, '10068', APT_HEAT_NEW)
    account_bills_2_rate_class(session, '10069', APT_HEAT_NEW)
    account_bills_2_rate_class(session, '10070', APT_HEAT_NEW)
    account_bills_2_rate_class(session, '10071', NONRESIDENTIAL_NONHEAT_NEW)
    account_bills_2_rate_class(session, '10072', NONRESIDENTIAL_HEAT_NEW)
    account_bills_2_rate_class(session, '10073', NONRESIDENTIAL_HEAT_NEW)
    account_bills_2_rate_class(session, '10074', NONRESIDENTIAL_NONHEAT_NEW)
    account_bills_2_rate_class(session, '10075', NONRESIDENTIAL_NONHEAT_NEW)
    account_bills_2_rate_class(session, '10076', NONRESIDENTIAL_NONHEAT_NEW)
    account_bills_2_rate_class(session, '10077', NONRESIDENTIAL_NONHEAT_NEW)
    account_bills_2_rate_class(session, '10078', NONRESIDENTIAL_NONHEAT_NEW)
    account_bills_2_rate_class(session, '10079', NONRESIDENTIAL_NONHEAT_NEW)
    account_bills_2_rate_class(session, '10080', NONRESIDENTIAL_NONHEAT_NEW)
    account_bills_2_rate_class(session, '10081', DELIVERY_INTERRUPT_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10082', APT_HEAT_NEW_PRINCE_GEORGE)
    # No bills for 10083
    account_bills_2_rate_class(session, '10084', APT_HEAT_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10085', APT_NONHEAT_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10086', APT_NONHEAT_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10087', APT_HEAT_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10088', APT_NONHEAT_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10089', APT_HEAT_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10090', APT_NONHEAT_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10091', APT_NONHEAT_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10092', APT_HEAT_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10093', APT_HEAT_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10094', APT_HEAT_PRINCE_GEORGE)
    # No bills for 10095
    account_bills_2_rate_class(session, '10096', APT_HEAT_NEW)
    account_bills_2_rate_class(session, '10097', APT_NONHEAT_NEW_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10098', APT_NONHEAT_NEW_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10099', APT_NONHEAT_NEW_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10100', APT_NONHEAT_NEW_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10101', APT_NONHEAT_NEW_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10102', APT_NONHEAT_NEW_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10103', APT_NONHEAT_NEW_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10104', APT_NONHEAT_NEW_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10105', APT_NONHEAT_NEW_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10106', APT_NONHEAT_NEW_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10107', APT_NONHEAT_NEW_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10108', APT_NONHEAT_NEW_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10109', APT_NONHEAT_NEW_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10110', APT_NONHEAT_NEW_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10111', APT_NONHEAT_NEW_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10112', APT_NONHEAT_NEW_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10113', APT_NONHEAT_NEW_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10114', APT_NONHEAT_NEW_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10115', APT_NONHEAT_NEW_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10116', APT_NONHEAT_NEW_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10117', APT_NONHEAT_NEW_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10118', APT_NONHEAT_NEW_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10119', APT_NONHEAT_NEW_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10120', APT_NONHEAT_NEW_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10121', APT_NONHEAT_NEW_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10122', APT_NONHEAT_NEW_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10123', APT_NONHEAT_NEW_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10124', APT_NONHEAT_NEW_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10125', APT_NONHEAT_NEW_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10126', APT_NONHEAT_NEW_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10127', APT_NONHEAT_NEW_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10128', APT_NONHEAT_NEW_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10129', APT_NONHEAT_NEW_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10130', APT_NONHEAT_NEW_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10131', APT_NONHEAT_NEW_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10132', APT_NONHEAT_NEW_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10133', APT_NONHEAT_NEW_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10134', APT_NONHEAT_NEW_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10135', APT_NONHEAT_NEW_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10136', APT_NONHEAT_NEW_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10137', APT_HEAT_NEW)
    account_bills_2_rate_class(session, '10138', APT_HEAT_NEW_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10139', APT_HEAT_NEW_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10140', APT_HEAT_MONTGOMERY)
    account_bills_2_rate_class(session, '10141', APT_HEAT_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10142', APT_NONHEAT_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10143', APT_NONHEAT_MONTGOMERY)
    account_bills_2_rate_class(session, '10144', RESIDENTIAL_HEAT_PRINCE_GEORGE)
    account_bills_2_rate_class(session, '10145', APT_NONHEAT_MONTGOMERY)
    account_bills_2_rate_class(session, '10146', APT_HEAT_NEW)
    account_bills_2_rate_class(session, '10147', APT_HEAT_MONTGOMERY)
    account_bills_2_rate_class(session, '10148', APT_HEAT_NEW_MONTGOMERY)
    # TODO 149-157 CA and PG&E
    account_bills_2_rate_class(session, '10158', APT_HEAT_NEW)
    # Todo: MAUI account_bills_2_rate_class(session, '10159', )
    account_bills_2_rate_class(session, '10160', NON_RESIDENTIAL_GS_D)
    account_bills_2_rate_class(session, '10160', NON_RESIDENTIAL_GS_ND)
    account_bills_2_rate_class(session, '20001', RESIDENTIAL_R_DC)
    account_bills_2_rate_class(session, '20002', RESIDENTIAL_R_DC)
    account_bills_2_rate_class(session, '20003', NONRESIDENTIAL_HEAT_Level_2)
    account_bills_2_rate_class(session, '20004', NON_RESIDENTIAL_GS_D)
    account_bills_2_rate_class(session, '20005', NONRESIDENTIAL_HEAT)
    account_bills_2_rate_class(session, '20006', RESIDENTIAL_R_DC)
    account_bills_2_rate_class(session, '20007', NONRESIDENTIAL_HEAT_Level_2)
    account_bills_2_rate_class(session, '20008', GENERAL_SERVICE_SCHEDULE_C_BALTIMORE)
    # TODO 20009
    account_bills_2_rate_class(session, '20010', COMMERCIAL_HEAT_COOL_DC_Level_2)

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
