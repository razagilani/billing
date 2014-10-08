from billing.reebill.reebill_processor import ReebillProcessor
from billing.reebill.utilbill_processor import UtilbillProcessor

class Process(UtilbillProcessor, ReebillProcessor):
    '''Deprecated wrapper around UtilbillProcessor and ReeBillProcessor.
    Uses of this class should be replaced with one of the those.
    '''
    def __init__(self, state_db, rate_structure_dao, billupload,
            nexus_util, bill_mailer, reebill_file_handler,
            ree_getter, journal_dao, logger=None):
        UtilbillProcessor.__init__(self, rate_structure_dao, billupload,
                                   nexus_util, logger=logger)
        ReebillProcessor.__init__(self, state_db, nexus_util, bill_mailer,
                                  reebill_file_handler, ree_getter, journal_dao,
                                  logger=logger)
