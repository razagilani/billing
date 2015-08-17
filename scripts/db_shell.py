#!/usr/bin/env python
"""Run this to start an IPython shell with everything set up to do database
queries with SQLAlchemy.
"""
from datetime import date, datetime, timedelta

import sqlalchemy as sa
import IPython

from core import init_config, init_model, init_altitude_db
from core.model import *
from core.altitude import *
from billentry.billentry_model import *
from brokerage.brokerage_model import *
from reebill.reebill_model import *

if __name__ == '__main__':
    init_config()
    init_model()
    init_altitude_db()
    s = Session()
    a = AltitudeSession()
    print '%s at %s' % (Session.bind.url,
                        s.execute("select * from alembic_version").scalar())
    print 'sa =', sa
    print 's =', s
    print 'a =', a
    IPython.start_ipython(argv=None, display_banner=False, user_ns=globals())
