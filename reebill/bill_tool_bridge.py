#!/usr/bin/python
'''
File: bill_tool_bridge.py
Description: Allows bill tool to be invoked as a CGI
'''
import site
site.addsitedir('/var/local/reebill/lib/python2.6/site-packages')

import sys
sys.stdout = sys.stderr

import traceback
import json

# CGI support
import cherrypy

# template support
import jinja2, os

import string

import ConfigParser

import MySQLdb

from billing.processing import process
from billing.processing import state
from billing.processing import fetch_bill_data as fbd
from billing.reebill import render

# TODO fixme
from billing import nexus_util as nu
from billing.nexus_util import NexusUtil

from billing import bill

from billing import json_util as ju

from skyliner.xml_utils import XMLUtils


from itertools import groupby


# TODO rename to ProcessBridge or something
class BillToolBridge:
    """ A monolithic class encapsulating the behavior to:  handle an incoming http request """
    """ and invoke bill processing code.  No business logic should reside here."""

    config = None

    # TODO: refactor config and share it between btb and bt 15413411
    def __init__(self):
        self.config = ConfigParser.RawConfigParser()
        config_file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)),'bill_tool_bridge.cfg')
        if not self.config.read(config_file_path):
            print "Creating config file"
            self.config.add_section('xmldb')
            self.config.set('xmldb', 'destination_prefix', 'http://[host]:8080/exist/rest/db/skyline/bills')
            self.config.set('xmldb', 'source_prefix', 'http://[host]:8080/exist/rest/db/skyline/bills')
            self.config.set('xmldb', 'password', '[password]')
            self.config.set('xmldb', 'user', 'prod')
            self.config.add_section('http')
            self.config.set('http', 'socket_port', '8185')
            self.config.set('http', 'socket_host', '10.0.0.250')
            self.config.add_section('billdb')
            self.config.set('billdb', 'rspath', '[root]db/skyline/ratestructure/')
            self.config.set('billdb', 'billpath', '[root]db/skyline/bills/')
            self.config.add_section('statedb')
            self.config.set('statedb', 'host', 'localhost')
            self.config.set('statedb', 'db', 'skyline')
            self.config.set('statedb', 'user', 'dev')
            self.config.set('statedb', 'password', '[password]')


            # Writing our configuration file to 'example.cfg'
            with open(config_file_path, 'wb') as new_config_file:
                self.config.write(new_config_file)

            self.config.read(config_file_path)



    @cherrypy.expose
    def copyactual(self, account, sequence, **args):

        try:
            p = process.Process(self.config)
            p.copy_actual(account, sequence)

        except Exception as e:
                return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        return json.dumps({'success': True})

    @cherrypy.expose
    def roll(self, account, sequence, **args):

        try:
            p = process.Process(self.config)
            p.roll_bill(account, sequence)

        except Exception as e:
                return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        return json.dumps({'success': True})

    @cherrypy.expose
    def pay(self, account, sequence, amount, **args):

        try:
            p = process.Process(self.config)
            p.pay_bill(account, sequence, amount)

        except Exception as e:
                return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        return json.dumps({'success': True})

    @cherrypy.expose
    def bindree(self, account, sequence, **args):

        from billing.processing import fetch_bill_data as fbd
        try:
            # TODO make args to fetch bill data optional
            fbd.fetch_bill_data(
                "http://duino-drop.appspot.com/",
                self.config.get("xmldb", "user"),
                self.config.get("xmldb", "password"),
                nu.NexusUtil("nexus").olap_id(account),
                "%s/%s/%s.xml" % (self.config.get("xmldb", "source_prefix"), account, sequence), 
                None,
                None,
                True
            )
        except Exception as e:
                return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        return json.dumps({'success': True})

    @cherrypy.expose
    def bindrs(self, account, sequence, **args):

        try:
            p = process.Process(self.config)
            p.bind_rate_structure(account, sequence)

        except Exception as e:
                return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        return json.dumps({'success': True})

    @cherrypy.expose
    def calc_reperiod(self, account, sequence, **args):

        try:
            p = process.Process(self.config)
            p.calculate_reperiod(account, sequence)

        except Exception as e:
                return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        return json.dumps({'success': True})

    @cherrypy.expose
    def calcstats(self, account, sequence, **args):

        try:
            p = process.Process(self.config)
            p.calculate_statistics(account, sequence)

        except Exception as e:
                return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        return json.dumps({'success': True})

    @cherrypy.expose
    def sum(self, account, sequence, **args):

        try:
            p = process.Process(self.config)
            p.sum_bill(account, sequence)

        except Exception as e:
                return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        return json.dumps({'success': True})
        
    @cherrypy.expose
    def issue(self, account, sequence, **args):


        try:
            process.Process().issue(None)

        except Exception as e:
                return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        return json.dumps({'success': True})



    @cherrypy.expose
    def render(self, account, sequence, **args):

        try:
            render.render(
                "%s/%s/%s.xml" % (self.config.get("xmldb", "source_prefix"), account, sequence), 
                self.config.get("billdb", "billpath")+ "%s/%s.pdf" % (account, sequence),
                "EmeraldCity-FullBleed-1.png,EmeraldCity-FullBleed-2.png",
                None,
            )
        except Exception as e:
                return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        return json.dumps({'success': True})

    @cherrypy.expose
    def commit(self, account, sequence, **args):

        try:

            p = process.Process(self.config)
            p.commit_rebill(account, sequence)

        except Exception as e:
                return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        return json.dumps({'success': True})

    @cherrypy.expose
    def issueToCustomer(self, account, sequence, **args):

        try:
            p = process.Process(self.config)
            p.issue_to_customer(account, sequence)

        except Exception as e:
                return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        return json.dumps({'success': True})


    @cherrypy.expose
    def listAccounts(self, **kwargs):
        accounts = []
        try:
            # eventually, this data will have to support pagination

            # instantiate stateDB
            statedb_config_section = self.config.items("statedb")
            state_db = state.StateDB(dict(statedb_config_section)) 

            accounts = state_db.listAccounts()

            # now get associated names from Nexus and add them to each account dictionary
            nu = NexusUtil()
            for account in accounts:
                all_names = NexusUtil().all("billing", account['account'])
                display_name = [account['account']]
                if 'codename' in all_names:
                    display_name.append(all_names['codename'])
                if 'casualname' in all_names:
                    display_name.append(all_names['casualname'])
                if 'primus' in all_names:
                    display_name.append(all_names['primus'])

                account['name'] = string.join(display_name, ' - ')



        except Exception as e:
                return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        return json.dumps({'success': True, 'rows':accounts})

    @cherrypy.expose
    def listSequences(self, account, **kwargs):
        sequences = []
        try:
            # instantiate stateDB
            statedb_config_section = self.config.items("statedb")
            state_db = state.StateDB(dict(statedb_config_section)) 

            # eventually, this data will have to support pagination
            sequences = state_db.listSequences(account)
        except Exception as e:
                return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        return json.dumps({'success': True, 'rows':sequences})

    @cherrypy.expose
    # TODO see 15415625 about the problem passing in service to get at a set of RSIs
    def listRSIs(self, account, sequence, service, **kwargs):

        try:
            the_bill = bill.Bill("%s/%s/%s.xml" % (self.config.get("xmldb", "source_prefix"), account, sequence))
            billdb = self.config.get("billdb", "rspath")
            # ok, this is the nasty - rsbinding is in utilbill and probably should be in details
            utilbills = the_bill.utilbill_summary_charges
            for (s, utilbill) in utilbills.items():
                rsbinding = utilbill.rsbinding
                if (s == service):
                    import yaml
                    import billing.processing.rate_structure as rs
                    rs_yaml = yaml.load(file(os.path.join(billdb, rsbinding, account, sequence+".yaml")))
                    # TODO: we can't json dumps RSIs, but the yaml is readily dumpable to JSON
                    # figure out best way to represent RSIs for web
                    #rate_structure = rs.RateStructure(rs_yaml)
                    return json.dumps({'success': True, 'rows':rs_yaml["rates"]})

        except Exception as e:
                return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})




    ################
    # Handle ubPeriods

    @cherrypy.expose
    def ubPeriods(self, account, sequence, **args):
        """
        Return all of the utilbill periods on a per service basis so that the forms may be
        dynamically created.
        """
        utilbill_periods = {}

        try:
            the_bill = bill.Bill("%s/%s/%s.xml" % (self.config.get("xmldb", "source_prefix"), account, sequence))

            ubSummary = the_bill.utilbill_summary_charges

            # TODO: just return utilbill summary charges and let extjs render the form
            for service, summary in ubSummary.items():
                utilbill_periods[service] = {
                    'begin':summary.begin,
                    'end':summary.end
                    }

        except Exception as e:
            return ju.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        return ju.dumps(utilbill_periods)

    @cherrypy.expose
    def setUBPeriod(self, account, sequence, service, begin, end, **args):
        """ 
        Utilbill period forms are dynamically created in browser, and post back to here individual periods.
        """ 

        try:
            the_bill = bill.Bill( "%s/%s/%s.xml" % (self.config.get("xmldb", "source_prefix"), account, sequence))

            ubSummary = the_bill.utilbill_summary_charges

            ubSummary[service].begin = begin
            ubSummary[service].end = end

            the_bill.utilbill_summary_charges = ubSummary

            XMLUtils().save_xml_file(the_bill.xml(), "%s/%s/%s.xml" % (self.config.get("xmldb", "source_prefix"), account, sequence),
                self.config.get("xmldb", "user"),
                self.config.get("xmldb", "password")
            )


        except Exception as e:
             return ju.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        return ju.dumps({'success':True})

    #
    ################

    ################
    # handle actual and hypothetical charges 

    @cherrypy.expose
    def actualCharges(self, service, account, sequence, **args):
        try:
            the_bill = bill.Bill("%s/%s/%s.xml" % (self.config.get("xmldb", "source_prefix"), account, sequence))
            actual_charges = the_bill.actual_charges_no_totals
            flattened_charges = self.flattenCharges(service, account, sequence, actual_charges, **args)

        except Exception as e:
            return ju.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        return ju.dumps({'success': True, 'rows': flattened_charges})

    @cherrypy.expose
    def hypotheticalCharges(self, service, account, sequence, **args):
        try:
            the_bill = bill.Bill("%s/%s/%s.xml" % (self.config.get("xmldb", "source_prefix"), account, sequence))
            hypothetical_charges = the_bill.hypothetical_charges_no_totals
            flattened_charges = self.flattenCharges(service, account, sequence, hypothetical_charges, **args)

        except Exception as e:
            return ju.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        return ju.dumps({'success': True, 'rows': flattened_charges})


    def flattenCharges(self, service, account, sequence, charges, **args):

        # flatten structure into an array of dictionaries, one for each charge
        # this has to be done because the grid editor is  looking for a flat table

        # This should probably not be done in bill.py, but rather by some helper object
        # if we don't want this cluttering up this wsgi method
        all_charges = []
        for (the_service, details) in charges.items():
            if (the_service == service):
                for chargegroup in details.chargegroups:
                    for charge in chargegroup.charges:
                        a_charge = {}
                        a_charge['chargegroup'] = chargegroup.type if hasattr(chargegroup,'type') else None
                        a_charge['rsbinding'] = charge.rsbinding if hasattr(charge, 'rsbinding') else None
                        a_charge['description'] = charge.description if hasattr(charge, 'description') else None
                        a_charge['quantity'] = charge.quantity if hasattr(charge, 'quantity') else None
                        a_charge['quantityunits'] = charge.quantityunits if hasattr(charge,'quantityunits') else None
                        a_charge['rate'] = charge.rate if hasattr(charge, 'rate') else None
                        a_charge['rateunits'] = charge.rateunits if hasattr(charge, 'rateunits') else None
                        a_charge['total'] = charge.total if hasattr(charge, 'total') else None

                        all_charges.append(a_charge)

        return all_charges


    @cherrypy.expose
    def saveActualCharges(self, service, account, sequence, rows, **args):
        try:
            the_bill = bill.Bill("%s/%s/%s.xml" % (self.config.get("xmldb", "source_prefix"), account, sequence))

            charge_items = ju.loads(rows)

            the_bill.actual_charges = self.nestCharges(service, account, sequence, charge_items)

            XMLUtils().save_xml_file(the_bill.xml(), "%s/%s/%s.xml" % (self.config.get("xmldb", "source_prefix"), account, sequence),
                self.config.get("xmldb", "user"),
                self.config.get("xmldb", "password")
            )

        except Exception as e:
            return ju.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        return ju.dumps({'success': True})

    @cherrypy.expose
    def saveHypotheticalCharges(self, service, account, sequence, rows, **args):
        try:
            the_bill = bill.Bill("%s/%s/%s.xml" % (self.config.get("xmldb", "source_prefix"), account, sequence))

            charge_items = ju.loads(rows)

            the_bill.hypothetical_charges = self.nestCharges(service, account, sequence, charge_items)

            XMLUtils().save_xml_file(the_bill.xml(), "%s/%s/%s.xml" % (self.config.get("xmldb", "source_prefix"), account, sequence),
                self.config.get("xmldb", "user"),
                self.config.get("xmldb", "password")
            )

        except Exception as e:
            return ju.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        return ju.dumps({'success': True})



    def nestCharges(self, service, account, sequence, the_charge_items, **args):

        # this code should go into process
        from billing.mutable_named_tuple import MutableNamedTuple

        details = {}

        details[service] = MutableNamedTuple()
        details[service].chargegroups = []

        for cgtype, charge_items in groupby(the_charge_items, key=lambda charge_item:charge_item['chargegroup']):
            chargegroup_mnt = MutableNamedTuple()
            chargegroup_mnt.type = cgtype
            chargegroup_mnt.charges = []
            for charge_item in charge_items:
                charge_mnt = MutableNamedTuple()
                charge_mnt.rsbinding = charge_item['rsbinding']
                charge_mnt.description = charge_item['description']
                charge_mnt.quantity = charge_item['quantity']
                charge_mnt.quantityunits = charge_item['quantityunits']
                charge_mnt.rate = charge_item['rate']
                charge_mnt.rateunits = charge_item['rateunits']
                charge_mnt.total = charge_item['total']
                chargegroup_mnt.charges.append(charge_mnt)

            # TODO refactor this into bill set charge_items such that the total property is created when absent.
            chargegroup_mnt.total = "0.00"

            details[service].chargegroups.append(chargegroup_mnt)

        return details


    ################
    # Handle measuredUsages

    @cherrypy.expose
    def ubMeasuredUsages(self, account, sequence, **args):
        """
        Return all of the measuredusages on a per service basis so that the forms may be
        dynamically created.
        """

        try:
            the_bill = bill.Bill("%s/%s/%s.xml" % (self.config.get("xmldb", "source_prefix"), account, sequence))

            ubMeasuredUsages = the_bill.measured_usage

        except Exception as e:
            return ju.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})


        return ju.dumps(ubMeasuredUsages)


    @cherrypy.expose
    def setMeter(self, account, sequence, service, meter_identifier, presentreaddate, priorreaddate):

        try:

            the_bill = bill.Bill( "%s/%s/%s.xml" % (self.config.get("xmldb", "source_prefix"), account, sequence))

            ubMeasuredUsages = the_bill.measured_usage

            # TODO: better way to filter for meter? The list comprehension should always be a list of one element
            # TODO: error conditions
            meter = [meter for meter in ubMeasuredUsages[service] if meter.identifier == meter_identifier]
            meter = meter[0] if meter else None
            if meter is None: 
                print "Should have found a single meter"
            else:
                meter.presentreaddate = presentreaddate
                meter.priorreaddate = priorreaddate

            the_bill.measured_usage = ubMeasuredUsages

            XMLUtils().save_xml_file(the_bill.xml(), "%s/%s/%s.xml" % (self.config.get("xmldb", "source_prefix"), account, sequence),
                self.config.get("xmldb", "user"),
                self.config.get("xmldb", "password")
            )

        except Exception as e:
             return ju.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        return ju.dumps({'success':True})

    @cherrypy.expose
    def setActualRegister(self, account, sequence, service, register_identifier, meter_identifier, total):

        try:

            the_bill = bill.Bill( "%s/%s/%s.xml" % (self.config.get("xmldb", "source_prefix"), account, sequence))

            ubMeasuredUsages = the_bill.measured_usage

            # TODO: better way to filter for register and meter? The list comprehension should always be a list of one element
            # TODO: error conditions
            meter = [meter for meter in ubMeasuredUsages[service] if meter.identifier == meter_identifier]
            meter = meter[0] if meter else None
            if meter is None: print "Should have found a single meter"
            # TODO: raise exception if no meter

            register = [register for register in meter.registers if register.identifier == register_identifier and register.shadow is False]
            register = register[0] if register else None
            if register is None: print "Should have found a single register"

            register.total = total

            the_bill.measured_usage = ubMeasuredUsages

            XMLUtils().save_xml_file(the_bill.xml(), "%s/%s/%s.xml" % (self.config.get("xmldb", "source_prefix"), account, sequence),
                self.config.get("xmldb", "user"),
                self.config.get("xmldb", "password")
            )

        except Exception as e:
             return ju.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        return ju.dumps({'success':True})


    #
    ################

    ################
    # Handle utility bill upload

    @cherrypy.expose
    def upload_utility_bill(self, account, begin_date, end_date, file_to_upload, **args):
        from billing.processing.billupload import BillUpload
        try:
            upload = BillUpload()
            # get Python file object and file name as string from the CherryPy
            # object 'file_to_upload', and pass those to BillUpload so it's
            # independent of CherryPy
            if upload.upload(account, begin_date, end_date,
                    file_to_upload.file, file_to_upload.filename) is True:
                return ju.dumps({'success':True})
            else:
                return ju.dumps({'success':False, 'errors':{'reason':'file upload failed', 'details':'Returned False'}})
        except Exception as e: 
             return ju.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

    #
    ################

 
    @cherrypy.expose
    def listUtilBills(self, start, limit, **args):
        # call getrows to actually query the database; return the result in
        # JSON format if it succeded or an error if it didn't
        try:
            result, totalCount = self.getUtilBillRows(int(start), int(limit))
            return ju.dumps({'success': True, 'rows':result,
                'results':totalCount})
        except Exception as e:
            # TODO: log errors?
            print >> sys.stderr, e
            #return '{success: false}'
            return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})
    
    '''Queries the 'skyline_dev' database on tyrell for account, start date, and
    end date of bills in a slice of the utilbills table; returns the slice and the
    total number of rows in the table (for paging).'''
    def getUtilBillRows(self, start, limit):
        conn = None
        try:
            # connect to database
            conn = MySQLdb.connect(host='tyrell', user='dev', passwd='dev', \
                    db='skyline_dev')
            
            # get appropriate slice of table
            cur = conn.cursor(MySQLdb.cursors.DictCursor)
            cur.execute('''select account, period_start, period_end 
                    from customer, utilbill
                    where customer.id = utilbill.customer_id
                    limit %d,%d''' % (start, limit))
            theSlice = cur.fetchall()
            
            # count total number of rows in the whole table (not just the slice)
            # note: this must be the exact same query as above, not just "select
            # count(*) from utilbill", which would count rows in utilbill that
            # have null ids even though they don't show up in the query above.
            cur.execute('''select count(*) as count from customer, utilbill
                    where customer.id = utilbill.customer_id''')
            totalCount = int(cur.fetchone()['count'])
            
            # return the slice (dictionary) and the overall count (integer)
            return theSlice, totalCount
        except MySQLdb.Error:
            # TODO is this kind of error checking good enough?
            print >> sys.stderr, "Database error"
            raise
        except:
            print >> sys.stderr, "Unexpected error:", sys.exc_info()[0]
            raise
        finally:
            if conn is not None:
                conn.close()

    @cherrypy.expose
    def getUtilBillImage(self, account, begin_date, end_date, **args):
        from billing.processing.billupload import BillUpload
        try:
            # TODO: put url here, instead of in billentry.js?
            upload = BillUpload()
            result = upload.getUtilBillImagePath(account, begin_date, end_date)
            return ju.dumps({'success':True, 'imageName':result})
        except Exception as e: 
             return ju.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

    @cherrypy.expose
    def getReeBillImage(self, account, sequence, **args):
        from billing.processing.billupload import BillUpload
        try:
            upload = BillUpload()
            result = upload.getReeBillImagePath(account, sequence)
            return ju.dumps({'success':True, 'imageName':result})
        except Exception as e: 
             return ju.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

bridge = BillToolBridge()

if __name__ == '__main__':

    # configure CherryPy
    local_conf = {
        '/' : {
            'tools.staticdir.root' :os.path.dirname(os.path.abspath(__file__)), 
            #'tools.staticdir.dir' : '',
            #'tools.staticdir.on' : True,
            'tools.expires.secs': 0,
            'tools.response_headers.on': True,
        },
    }
    cherrypy.config.update({ 'server.socket_host': bridge.config.get("http", "socket_host"),
                             'server.socket_port': int(bridge.config.get("http", "socket_port")),
                             })
    cherrypy.quickstart(bridge, "/", config = local_conf)
else:
    # WSGI Mode
    cherrypy.config.update({'environment': 'embedded'})

    if cherrypy.__version__.startswith('3.0') and cherrypy.engine.state == 0:
        cherrypy.engine.start(blocking=False)
        atexit.register(cherrypy.engine.stop)

    application = cherrypy.Application(bridge, script_name=None, config=None)

