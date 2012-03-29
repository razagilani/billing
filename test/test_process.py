#!/usr/bin/pytho.date(),
import sys
import unittest
from StringIO import StringIO
import ConfigParser
import pymongo
from skyliner.splinter import Splinter
from skyliner.skymap.monguru import Monguru
from datetime import date, datetime, timedelta
from billing import dateutils, mongo
from billing.processing import rate_structure
from billing.processing.process import Process
from billing.processing.state import StateDB
from billing.processing.db_objects import ReeBill, Customer, UtilBill
from decimal import Decimal
from billing.dictutils import deep_map
import copy
import MySQLdb
from billing.mongo_utils import python_convert

class ProcessTest(unittest.TestCase):
    def setUp(self):
        # everything needed to create a Process object
        config_file = StringIO('''[runtime]\nintegrate_skyline_backend = true''')
        self.config = ConfigParser.RawConfigParser()
        self.config.readfp(config_file)
        self.reebill_dao = mongo.ReebillDAO({
            'billpath': '/db-dev/skyline/bills/',
            'database': 'test',
            'utilitybillpath': '/db-dev/skyline/utilitybills/',
            'collection': 'test_reebills',
            'host': 'localhost',
            'port': 27017
        })
        self.rate_structure_dao = rate_structure.RateStructureDAO({
            'database': 'test',
            'collection': 'ratestructure',
            'host': 'localhost',
            'port': 27017
        })
        self.splinter = Splinter('http://duino-drop.appspot.com/', 'tyrell',
                'dev')
        self.monguru = Monguru('tyrell', 'dev')
        
        # temporary hack to get a bill that's always the same
        # this bill came straight out of mongo (except for .date() applied to
        # datetimes)
        ISODate = lambda s: datetime.strptime(s, dateutils.ISO_8601_DATETIME)
        true, false = True, False
        self.example_bill = {
            "_id" : {
                "account" : "10003",
                "branch" : 0,
                "sequence" : 1
            },
            "ree_charges" : 32.6,
            "sequence" : 1,
            "ree_value" : 65.207194857,
            "discount_rate" : 0.5,
            "issue_date" : ISODate("2010-02-15T00:00:00Z").date(),
            "utilbills" : [
                {
                    "actual_chargegroups" : {
                        "All Charges" : [
                            {
                                "description" : "System Charge",
                                "total" : 11.2,
                                "uuid" : "dd7f02ca-41e8-4110-91da-39d56ba0fb5d",
                                "quantity" : 1,
                                "rsi_binding" : "SYSTEM_CHARGE"
                            },
                            {
                                "rsi_binding" : "DISTRIBUTION_CHARGE",
                                "description" : "Distribution charge for all therms",
                                "rate_units" : "dollars",
                                "rate" : 0.2939,
                                "quantity_units" : "therms",
                                "total" : 106.24485,
                                "quantity" : 361.5,
                                "uuid" : "44316cd1-8cb1-4135-8490-98ee9f28b8db"
                            },
                            {
                                "rsi_binding" : "PGC",
                                "description" : "Purchased Gas Charge",
                                "rate_units" : "dollars",
                                "rate" : 1.0209,
                                "quantity_units" : "therms",
                                "total" : 369.05535,
                                "quantity" : 361.5,
                                "uuid" : "88983907-7f47-40f9-b603-3a769e531182"
                            },
                            {
                                "rsi_binding" : "RIGHT_OF_WAY",
                                "description" : "DC Rights-of-Way Fee",
                                "rate_units" : "dollars",
                                "rate" : 0.0304011,
                                "quantity_units" : "therms",
                                "total" : 10.98999765,
                                "quantity" : 361.5,
                                "uuid" : "23a8825e-3702-4663-9131-a007ec593473"
                            },
                            {
                                "rsi_binding" : "SETF",
                                "description" : "Sustainable Energy Trust Fund",
                                "rate_units" : "dollars",
                                "rate" : 0.012,
                                "quantity_units" : "therms",
                                "total" : 4.338,
                                "quantity" : 361.5,
                                "uuid" : "06f08dc7-563e-47da-88b0-fb50d066520a"
                            },
                            {
                                "rsi_binding" : "EATF",
                                "description" : "DC Energy Assistance Trust Fund",
                                "rate_units" : "dollars",
                                "rate" : 0.006,
                                "quantity_units" : "therms",
                                "total" : 2.169,
                                "quantity" : 361.5,
                                "uuid" : "3d8c532e-0387-4772-bb36-8d93834cd42d"
                            },
                            {
                                "rsi_binding" : "SALES_TAX",
                                "description" : "Sales tax",
                                "rate_units" : "dollars",
                                "rate" : 0.06,
                                "quantity_units" : "dollars",
                                "total" : 31.926663159,
                                "quantity" : 532.11105265,
                                "uuid" : "31d66cbb-2024-4f52-96d6-404b7faade82"
                            },
                            {
                                "rsi_binding" : "DELIVERY_TAX",
                                "description" : "Delivery tax",
                                "rate_units" : "dollars",
                                "rate" : 0.07777,
                                "quantity_units" : "therms",
                                "total" : 28.113855,
                                "quantity" : 361.5,
                                "uuid" : "3434e28c-f287-4ebf-9708-0c3661d259ea"
                            }
                        ]
                    },
                    "ree_charges" : 32.6,
                    "service" : "Gas",
                    "utility_name" : "washgas",
                    "ree_savings" : 32.61,
                    "hypothetical_chargegroups" : {
                        "All Charges" : [
                            {
                                "description" : "System Charge",
                                "total" : 11.2,
                                "uuid" : "64d14133-83a1-4a2c-987b-9f9587ae1685",
                                "quantity" : 1,
                                "rsi_binding" : "SYSTEM_CHARGE"
                            },
                            {
                                "rsi_binding" : "DISTRIBUTION_CHARGE",
                                "description" : "Distribution charge for all therms",
                                "rate_units" : "dollars",
                                "rate" : 0.2939,
                                "quantity_units" : "therms",
                                "total" : 118.791678675,
                                "quantity" : 404.190808694,
                                "uuid" : "865d75c4-4222-48d0-bb43-49cca2d6fea3"
                            },
                            {
                                "rsi_binding" : "PGC",
                                "description" : "Purchased Gas Charge",
                                "rate_units" : "dollars",
                                "rate" : 1.0209,
                                "quantity_units" : "therms",
                                "total" : 412.638396595,
                                "quantity" : 404.190808694,
                                "uuid" : "ecf3161e-6386-4b8f-a0f7-a66fdc9d37cb"
                            },
                            {
                                "rsi_binding" : "RIGHT_OF_WAY",
                                "description" : "DC Rights-of-Way Fee",
                                "rate_units" : "dollars",
                                "rate" : 0.0304011,
                                "quantity_units" : "therms",
                                "total" : 12.2878451942,
                                "quantity" : 404.190808694,
                                "uuid" : "ad11e36d-7e46-4541-b8da-023b3ca52ff2"
                            },
                            {
                                "rsi_binding" : "SETF",
                                "description" : "Sustainable Energy Trust Fund",
                                "rate_units" : "dollars",
                                "rate" : 0.012,
                                "quantity_units" : "therms",
                                "total" : 4.85028970432,
                                "quantity" : 404.190808694,
                                "uuid" : "c0c06e1a-a0de-4e4f-a9d2-22a95c75b93a"
                            },
                            {
                                "rsi_binding" : "EATF",
                                "description" : "DC Energy Assistance Trust Fund",
                                "rate_units" : "dollars",
                                "rate" : 0.006,
                                "quantity_units" : "therms",
                                "total" : 2.42514485216,
                                "quantity" : 404.190808694,
                                "uuid" : "837d93d2-a27a-448a-8f02-f39d4b62f007"
                            },
                            {
                                "rsi_binding" : "SALES_TAX",
                                "description" : "Sales tax",
                                "rate_units" : "dollars",
                                "rate" : 0.06,
                                "quantity_units" : "dollars",
                                "total" : 35.6176364528,
                                "quantity" : 593.627274213,
                                "uuid" : "34bf0295-c290-422b-9741-6c7532cc3c58"
                            },
                            {
                                "rsi_binding" : "DELIVERY_TAX",
                                "description" : "Delivery tax",
                                "rate_units" : "dollars",
                                "rate" : 0.07777,
                                "quantity_units" : "therms",
                                "total" : 31.4339191921,
                                "quantity" : 404.190808694,
                                "uuid" : "873cc53b-7db6-44fe-a2d0-44d657810dfa"
                            }
                        ]
                    },
                    "ree_value" : 65.207194857,
                    "meters" : [
                        {
                            "present_read_date" : ISODate("2010-08-13T00:00:00Z").date(),
                            "registers" : [
                                {
                                    "register_binding" : "REG_TOTAL",
                                    "quantity" : 361.5,
                                    "description" : "Therms",
                                    "shadow" : false,
                                    "identifier" : "M60324",
                                    "type" : "total",
                                    "quantity_units" : "therms"
                                },
                                {
                                    "register_binding" : "REG_TOTAL",
                                    "quantity" : 42.6908086936,
                                    "description" : "Therms",
                                    "shadow" : true,
                                    "identifier" : "M60324",
                                    "type" : "total",
                                    "quantity_units" : "therms"
                                }
                            ],
                            "estimated" : false,
                            "prior_read_date" : ISODate("2010-07-15T00:00:00Z").date(),
                            "identifier" : "M60324"
                        }
                    ],
                    "actual_total" : 564.037715809,
                    "period_end" : ISODate("2010-08-13T00:00:00Z").date(),
                    "period_begin" : ISODate("2010-07-15T00:00:00Z").date(),
                    "hypothetical_total" : 629.244910666,
                    "rate_structure_binding" : "DC Non Residential Non Heat",
                    "billingaddress" : {
                        "postalcode" : "20910",
                        "city" : "Silver Spring",
                        "state" : "MD",
                        "addressee" : "Managing Member Monroe Towers",
                        "street" : "3501 13TH ST NW LLC"
                    },
                    "serviceaddress" : {
                        "postalcode" : "20010",
                        "city" : "Washington",
                        "state" : "DC",
                        "addressee" : "Monroe Towers",
                        "street" : "3501 13TH ST NW #WH"
                    }
                }
            ],
            "payment_received" : 0,
            "branch" : 0,
            "period_end" : ISODate("2010-08-13T00:00:00Z").date(),
            "balance_forward" : 0,
            "due_date" : ISODate("2010-03-17T00:00:00Z").date(),
            "service_address" : {
                "sa_city" : "Washington",
                "sa_state" : "DC",
                "sa_addressee" : "Monroe Towers",
                "sa_postal_code" : "20010",
                "sa_street1" : "3501 13TH ST NW #WH"
            },
            "total_adjustment" : 0,
            "ree_savings" : 32.61,
            "statistics" : {
                "renewable_utilization" : 0.11,
                "total_co2_offset" : 574.6,
                "conventional_consumed" : 36150000,
                "conventional_utilization" : 0.89,
                "consumption_trend" : [
                    {
                        "month" : "Nov",
                        "quantity" : 0
                    },
                    {
                        "month" : "Dec",
                        "quantity" : 0
                    },
                    {
                        "month" : "Jan",
                        "quantity" : 0
                    },
                    {
                        "month" : "Feb",
                        "quantity" : 0
                    },
                    {
                        "month" : "Mar",
                        "quantity" : 0
                    },
                    {
                        "month" : "Apr",
                        "quantity" : 0
                    },
                    {
                        "month" : "May",
                        "quantity" : 0
                    },
                    {
                        "month" : "Jun",
                        "quantity" : 0
                    },
                    {
                        "month" : "Jul",
                        "quantity" : 0
                    },
                    {
                        "month" : "Aug",
                        "quantity" : 42.7
                    },
                    {
                        "month" : "Sep",
                        "quantity" : 222.1
                    },
                    {
                        "month" : "Oct",
                        "quantity" : 0
                    }
                ],
                "renewable_consumed" : 4269081,
                "total_trees" : 0,
                "co2_offset" : 574.618285016,
                "total_renewable_consumed" : 4269081,
                "total_savings" : 32.61
            },
            "balance_due" : 32.6,
            "account" : "10003",
            "prior_balance" : 0,
            "hypothetical_total" : 629.244910666,
            "actual_total" : 564.037715809,
            "period_begin" : ISODate("2010-07-15T00:00:00Z").date(),
            "billing_address" : {
                "ba_addressee" : "Managing Member Monroe Towers",
                "ba_state" : "MD",
                "ba_city" : "Silver Spring",
                "ba_street1" : "3501 13TH ST NW LLC",
                "ba_postal_code" : "20910"
            }
        }

        self.example_urs = {
            "_id" : {
                "type" : "URS",
                "rate_structure_name" : "101 - Residential Service",
                "utility_name" : "piedmont"
            },
            "registers" : [
                {
                    "register_binding" : "REG_THERMS",
                    "description" : "Total therm register",
                    "uuid" : "af65077e-01a9-11e1-af85-002421e88ffb",
                    "quantityunits" : "therm",
                    "quantity" : "0",
                    "quantity_units" : "therm"
                }
            ],
            "rates" : [
                {
                    "rate" : "10.00",
                    "rsi_binding" : "CUSTOMER_CHARGE",
                    "uuid" : "af650184-01a9-11e1-af85-002421e88ffb",
                    "quantity" : 1,
                    "description" : "Monthly flat charge"
                },
                {
                    "rsi_binding" : "PER_THERM_RATE",
                    "quantity_units" : "therms",
                    "quantity" : "REG_THERMS.quantity",
                    "uuid" : "af650418-01a9-11e1-af85-002421e88ffb",
                    "rate" : "0.923333333333",
                    "roundrule" : "ROUND_DOWN",
                    "description" : "Rate per Therm"
                },
                {
                    "rsi_binding" : "EXCISE_TAX",
                    "quantity_units" : "Therms",
                    "rate_units" : "dollars",
                    "uuid" : "af6505d0-01a9-11e1-af85-002421e88ffb",
                    "rate" : "0.047 if REG_THERMS.quantity < 200 else 0.035 if REG_THERMS.quantity >= 200 and REG_THERMS.quantity < 15000 else 0.024 if REG_THERMS.quantity >=15000 and REG_THERMS.quantity < 60000 else 0.015 if REG_THERMS.quantity >= 60000 and REG_THERMS.quantity < 500000 else 0.003",
                    "quantity" : "REG_THERMS.quantity",
                    "description" : "Declining block tax"
                }
            ]
        }

        self.example_cprs = {
            "_id" : {
                "account" : "10001",
                "sequence" : 15,
                "utility_name" : "washgas",
                "rate_structure_name" : "COMMERCIAL_HEAT-COOL",
                "branch" : 0,
                "type" : "CPRS"
            },
            "rates" : [
                {
                    "total" : 36.25,
                    "rate" : "36.25",
                    "rsi_binding" : "SYSTEM_CHARGE",
                    "uuid" : "af2ac500-01a9-11e1-af85-002421e88ffb",
                    "quantity" : "1"
                },
                {
                    "rsi_binding" : "ENERGY_FIRST_BLOCK",
                    "uuid" : "af2ac7e4-01a9-11e1-af85-002421e88ffb",
                    "rate_units" : "dollars",
                    "rate" : "0.2876",
                    "quantity_units" : "therms",
                    "quantity" : "(300) if (REG_TOTAL.quantity > 300) else (REG_TOTAL.quantity)"
                },
                {
                    "rsi_binding" : "ENERGY_SECOND_BLOCK",
                    "uuid" : "af2ac9ba-01a9-11e1-af85-002421e88ffb",
                    "quantity" : "(6700) if (REG_TOTAL.quantity > 7000) else ( (0) if (REG_TOTAL.quantity <300) else (REG_TOTAL.quantity-300  ) )",
                    "rate_units" : "dollars",
                    "rate" : "0.187",
                    "roundrule" : "ROUND_UP",
                    "quantity_units" : "therms"
                },
                {
                    "rsi_binding" : "ENERGY_REMAINDER_BLOCK",
                    "uuid" : "af2acba4-01a9-11e1-af85-002421e88ffb",
                    "rate_units" : "dollars",
                    "rate" : "0.1573",
                    "quantity_units" : "therms",
                    "quantity" : "(REG_TOTAL.quantity - 7000) if (REG_TOTAL.quantity > 7000 ) else (0)"
                },
                {
                    "rsi_binding" : "MD_STATE_SALES_TAX",
                    "uuid" : "af2acd8e-01a9-11e1-af85-002421e88ffb",
                    "rate_units" : "percent",
                    "rate" : "0.06",
                    "quantity_units" : "dollars",
                    "quantity" : "SYSTEM_CHARGE.total + ENERGY_FIRST_BLOCK.total + ENERGY_SECOND_BLOCK.total + ENERGY_REMAINDER_BLOCK.total"
                },
                {
                    "total" : 0.2,
                    "rate" : "0.2",
                    "rsi_binding" : "MD_GROSS_RECEIPTS_SURCHARGE",
                    "uuid" : "af2acf78-01a9-11e1-af85-002421e88ffb",
                    "quantity" : "1"
                },
                {
                    "rsi_binding" : "PG_COUNTY_ENERGY_TAX",
                    "uuid" : "af2ad18a-01a9-11e1-af85-002421e88ffb",
                    "rate_units" : "dollars",
                    "rate" : "0.07",
                    "quantity_units" : "therms",
                    "quantity" : "REG_TOTAL.quantity"
                },
                {
                    "rsi_binding" : "SUPPLY_COMMODITY",
                    "uuid" : "af2ad374-01a9-11e1-af85-002421e88ffb",
                    "rate_units" : "dollars",
                    "rate" : "0.86",
                    "quantity_units" : "therms",
                    "quantity" : "REG_TOTAL.quantity"
                },
                {
                    "rsi_binding" : "SUPPLY_BALANCING",
                    "uuid" : "af2ad586-01a9-11e1-af85-002421e88ffb",
                    "rate_units" : "dollars",
                    "rate" : "0.0138",
                    "quantity_units" : "therms",
                    "quantity" : "REG_TOTAL.quantity"
                },
                {
                    "rsi_binding" : "MD_SUPPLY_SALES_TAX",
                    "uuid" : "af2ad770-01a9-11e1-af85-002421e88ffb",
                    "rate_units" : "percent",
                    "rate" : "0.06",
                    "quantity_units" : "dollars",
                    "quantity" : "SUPPLY_COMMODITY.total + SUPPLY_BALANCING.total"
                }
            ]
        }

        # customer database ("test" database has already been created with
        # empty customer table)
        statedb_config = {
            'host': 'localhost',
            'database': 'test',
            'user': 'dev',
            'password': 'dev'
        }

        # clear out tables in mysql test database (not relying on StateDB)
        mysql_connection = MySQLdb.connect('localhost', 'dev', 'dev', 'test') # host, username, password, db
        c = mysql_connection.cursor()
        c.execute("delete from payment")
        c.execute("delete from utilbill")
        c.execute("delete from rebill")
        c.execute("delete from customer")
        # (note that status_days_since, status_unbilled are views and you
        # neither can nor need to delete from them)
        mysql_connection.commit()

        # insert one customer
        self.state_db = StateDB(statedb_config)
        session = self.state_db.session()
        customer = Customer('Test Customer', '99999', .12, .34)
        session.add(customer)
        session.commit()

    def tearDown(self):
        '''This gets run even if a test fails.'''
        # clear out mongo test database
        mongo_connection = pymongo.Connection('localhost', 27017)
        mongo_connection.drop_database('test')

        # clear out tables in mysql test database (not relying on StateDB)
        mysql_connection = MySQLdb.connect('localhost', 'dev', 'dev', 'test') # host, username, password, db
        c = mysql_connection.cursor()
        c.execute("delete from payment")
        c.execute("delete from utilbill")
        c.execute("delete from rebill")
        c.execute("delete from customer")
        mysql_connection.commit()

    def test_get_late_charge(self):
        '''Tests computation of late charges (without rolling bills).'''
        try:
            session = self.state_db.session()
            process = Process(self.config, self.state_db, self.reebill_dao,
                    self.rate_structure_dao, self.splinter, self.monguru)

            # first bill ever has late fee of 0
            bill1 = mongo.MongoReebill(deep_map(mongo.float_to_decimal,
                    python_convert(copy.deepcopy(self.example_bill))))
            bill1.account = '99999'
            bill1.sequence = 1
            bill1.balance_forward = Decimal('100.')
            self.assertEqual(0, process.get_late_charge(session, bill1, date(2011,12,31)))
            self.assertEqual(0, process.get_late_charge(session, bill1, date(2012,1,1)))
            self.assertEqual(0, process.get_late_charge(session, bill1, date(2012,1,2)))
            self.assertEqual(0, process.get_late_charge(session, bill1, date(2012,2,1)))
            self.assertEqual(0, process.get_late_charge(session, bill1, date(2012,2,2)))

            # issue bill 1, so a later bill can have a late charge based on the
            # customer's failure to pay it by the due date. (it must be saved
            # in both mongo and mysql to be issued.) due date is automatically
            # set to 30 days after issue date.
            self.reebill_dao.save_reebill(bill1)
            self.state_db.new_rebill(session, bill1.account, bill1.sequence)
            process.issue(session, bill1.account, bill1.sequence,
                    issue_date=date(2012,1,1))
            # since process.issue() only modifies databases, bill1 must be
            # re-loaded from mongo to reflect its new issue date
            bill1 = self.reebill_dao.load_reebill(bill1.account, bill1.sequence)
            assert bill1.due_date == date(2012,1,31)

            # after bill1 is created, it must be "summed" to get it into a
            # usable state (in particular, it needs a late charge). that
            # requires a sequence 0 template bill. put one into mongo and then
            # sum bill1.
            bill0 = mongo.MongoReebill(deep_map(mongo.float_to_decimal,
                    python_convert(copy.deepcopy(self.example_bill))))
            bill0.account = '99999'
            bill0.sequence = 0
            process.sum_bill(session, bill0, bill1)

            # but sum_bill() destroys bill1's balance_due, so reset it to
            # the right value, and save it in mongo
            bill1.balance_due = Decimal('100')
            self.reebill_dao.save_reebill(bill1)

            # create second bill (not by rolling, because process.roll_bill()
            # is currently a huge untested mess, and get_late_charge() should
            # be tested in isolation.) note that bill1's late charge is set in
            # mongo by process.issue().
            bill2 = mongo.MongoReebill(deep_map(mongo.float_to_decimal,
                    python_convert(copy.deepcopy(self.example_bill))))
            bill2.account = '99999'
            bill2.sequence = 2
            bill2.balance_due = Decimal('200.')

            # bill2's late charge should be 0 before bill1's due date and non-0
            # after
            import pdb; pdb.set_trace()
            self.assertEqual(0, process.get_late_charge(session, bill2, date(2011,12,31)))
            self.assertEqual(0, process.get_late_charge(session, bill2, date(2012,1,2)))
            self.assertEqual(0, process.get_late_charge(session, bill2, date(2012,1,31)))
            self.assertEqual(134, process.get_late_charge(session, bill2, date(2012,2,1)))
            self.assertEqual(134, process.get_late_charge(session, bill2, date(2012,2,2)))
            self.assertEqual(134, process.get_late_charge(session, bill2, date(2013,1,1)))

            session.commit()
        except:
            session.rollback()
            raise

#    def test_roll_late_fee(self):
#        '''Tests the behavior of Process.roll_bill with respect to calculating
#        a late fee.'''
#        try:
#            session = self.state_db.session()
#
#            process = Process(self.config, self.state_db, self.reebill_dao,
#                    self.rate_structure_dao, self.splinter, self.monguru)
#
#            # TODO state db
#
#            # set up a bill with a balance forward and no late fee
#            bill = mongo.MongoReebill(python_convert(copy.deepcopy(self.example_bill)))
#            bill.balance_forward = 100.
#            bill.late_charges = Decimal('0.00')
#            bill.account = '99999'
#            bill.sequence = 1 # needs to be last sequence
#            bill.issue_date = date(2012,3,15)
#
#            # create reebill for sequence 0 in mysql (and it must be issued,
#            # because we need its issue date to compute late charge)
#            customer = session.query(Customer).filter(Customer.account==bill.account).one()
#            #r = ReeBill(customer, bill.sequence)
#            #r.issued = 1
#            #session.add(r)
#            # need to create relationships in mysql too
#            #
#            u = UtilBill(customer, UtilBill.Complete, 'gas',
#                    period_start=date(2012,1,1), period_end=date(2012,2,1),
#                    processed=1, date_received=datetime(2012,2,15))
#            session.add(u)
#
#            # put fake URS & CPRS into db (UPRS not needed), so they can be
#            # combined in load_probable_rs()
#            urs = python_convert(copy.deepcopy(self.example_cprs))
#            urs["_id"] = {
#                "utility_name" : "washgas",
#                "rate_structure_name" : "DC Non Residential Non Heat",
#                "type" : "URS"
#            },
#            cprs = python_convert(copy.deepcopy(self.example_cprs))
#            cprs["_id"] = {
#                "account" : '99999',
#                "sequence" : 1,
#                "utility_name" : "washgas",
#                "rate_structure_name" : "DC Non Residential Non Heat",
#                "branch" : 0,
#                "type" : "CPRS"
#            },
#            self.rate_structure_dao.save_urs('washgas', "DC Non Residential Non Heat",
#                    None, None, self.example_urs)
#            self.rate_structure_dao.save_cprs(bill.account,
#                    bill.sequence, bill.branch, 'washgas',
#                    'DC Non Residential Non Heat', self.example_cprs)
#
#            # roll the bill
#            process.roll_bill(session, bill)
#
#            # sequence should be incremented, and late charges should be late
#            # charge rate * previous late charges
#            self.assertEqual(bill.sequence, 2)
#            self.assertEqual(bill.late_charges, 0)
#
#
#
#            # to roll the reebill again, the old bill must be issued, we need
#            # another reebill and utilbill in MySQL, and we need a CPRS in
#            # Mongo
#            x = session.query(ReeBill).all()
#            r2 = ReeBill(customer, bill.sequence)
#            r2.issued = 1
#            import pdb; pdb.set_trace();
#            session.add(r2)
#            session.add(UtilBill(customer, UtilBill.Complete, 'gas',
#                    period_start=date(2012,2,1), period_end=date(2012,3,1),
#                    processed=1, reebill=r2, date_received=datetime(2012,3,15)))
#            #cprs["_id"] = {
#                #"account" : '99999',
#                #"sequence" : 2,
#                #"utility_name" : "washgas",
#                #"rate_structure_name" : "DC Non Residential Non Heat",
#                #"branch" : 0,
#                #"type" : "CPRS"
#            #},
#            #self.rate_structure_dao.save_cprs(bill.account,
#                    #bill.sequence, bill.branch, 'washgas',
#                    #'DC Non Residential Non Heat', self.example_cprs)
#
#            ## now add a late charge to the bill and roll it again: late charge
#            ## should be multiplied by late charge rate
#            ##bill.late_charges = 100
#            #process.roll_bill(session, bill)
#
#            session.commit()
#        except:
#            session.rollback()
#            raise

if __name__ == '__main__':
    unittest.main(failfast=True)
