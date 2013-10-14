import unittest
from datetime import date
from billing.util.holidays import *

class HolidaysTest(unittest.TestCase):
    def test_all_holidays(self):
        # source of holiday dates:
        # http://www.opm.gov/oca/worksch/html/holiday.asp
        # (note that some sources, such as
        # http://www.opm.gov/Operating_Status_Schedules/fedhol/2011.asp
        # report federal employee vacation days, which may differ from the
        # holidays themselves. we assume that utility billing holidays are the
        # actual holiday dates.)
        
        # 2013
        newyear11 = date(2011, 1, 1)
        mlk11 = date(2011, 1, 17)
        washington11 = date(2011, 2, 21)
        memorial11 = date(2011, 5, 30)
        independence11 = date(2011, 7, 4)
        labor11 = date(2011, 9, 5)
        columbus11 = date(2011, 10, 10)
        veterans11 = date(2011, 11, 11)
        thanks11 = date(2011, 11, 24)
        xmas11 = date(2011, 12, 25)
        all_2011 = set([newyear11, mlk11, washington11, memorial11,
            independence11, labor11, columbus11, veterans11, thanks11, xmas11])
        self.assertEquals(all_2011, all_holidays(2011))
        
        # 2012
        newyear12 = date(2012, 1, 1)
        mlk12 = date(2012, 1, 16)
        washington12 = date(2012, 2, 20)
        memorial12 = date(2012, 5, 28)
        independence12 = date(2012, 7, 4)
        labor12 = date(2012, 9, 3)
        columbus12 = date(2012, 10, 8)
        veterans12 = date(2012, 11, 11)
        thanks12 = date(2012, 11, 22)
        xmas12 = date(2012, 12, 25)
        all_2012 = set([newyear12, mlk12, washington12, memorial12,
            independence12, labor12, columbus12, veterans12, thanks12, xmas12])
        self.assertEquals(all_2012, all_holidays(2012))
        
        # 2013
        # manually checked
        newyear13 = date(2013, 1, 1)
        mlk13 = date(2013, 1, 21)
        washington13 = date(2013, 2, 18)
        memorial13 = date(2013, 5, 27)
        independence13 = date(2013, 7, 4)
        labor13 = date(2013, 9, 2)
        columbus13 = date(2013, 10, 14)
        veterans13 = date(2013, 11, 11)
        thanks13 = date(2013, 11, 28)
        xmas13 = date(2013, 12, 25)
        all_2013 = set([newyear13, mlk13, washington13, memorial13,
            independence13, labor13, columbus13, veterans13, thanks13, xmas13])
        self.assertEquals(all_2013, all_holidays(2013))

if __name__ == '__main__':
    unittest.main()
