from processing.reebill_procesor import ReebillProcessor
from processing.utilbill_procesor import UtilbillProcessor



class Process(UtilbillProcessor, ReebillProcessor):
    '''Deprecated wrapper around UtilbillProcessor and ReeBillProcessor.
    Uses of this class should be replaced with one of the those.
    '''
    def __init__(self, state_db, rate_structure_dao, billupload,
            nexus_util, bill_mailer, reebill_file_handler,
            ree_getter, journal_dao, splinter=None, logger=None):
        UtilbillProcessor.__init__(self, rate_structure_dao, billupload,
                                   nexus_util, journal_dao, logger=logger)
        ReebillProcessor.__init__(self, state_db, rate_structure_dao,
                                  billupload, nexus_util, bill_mailer, reebill_file_handler,
                                  ree_getter, journal_dao,
                                  splinter=splinter, logger=logger)
