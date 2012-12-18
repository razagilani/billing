import tablib
from datetime import date
from collections import OrderedDict
import argparse
import os.path
import traceback
from billing.processing import state
from billing.processing import mongo
from billing.processing.session_contextmanager import DBSession

class ColumnPack:
    def __init__(self, name_list, getter, total_funcs, formatters = None):
        '''Create a column describing a piece of data
        
        name_list can be either a single name or a list of them
        getter is a function that takes:
        a MongoReebill
        a service string
        a utilbill handle
        a mongo utilbill document
        a mysql utilbill row
        and returns a single value if name_list is a single name,
        or a tuple of values matching the tuple in name_list
        total_funcs describes the functions used to summarize each column.
        it should be a single function if name_list is a single name,
        or a tuple of functions for each column
        Similarly for the optional formatters; there is one per column.
        '''
        self.name_list = name_list
        self.getter = getter
        self.total_func_dict = OrderedDict()
        #Make dictionaries from the input functions and formatters to ease access
        if isinstance(name_list, str):
            self.total_func_dict[name_list] = total_funcs
        else:
            for i in xrange(len(name_list)):
                self.total_func_dict[name_list[i]] = total_funcs[i]
        self.format_dict = OrderedDict()
        if isinstance(name_list, str):
            self.format_dict[name_list] = formatters
        else:
            for i in xrange(len(name_list)):
                if formatters is None:
                    self.format_dict[name_list[i]] = None
                else:
                    self.format_dict[formatters[i]] = formatters[i]
                    
    def get_stats(self, reebill, service, reebill_ub, mub, ub):
        '''Get the stats for the reebill given for the columns described in this pack'''
        #Get the result
        res = self.getter(reebill, service, reebill_ub, mub, ub)
        #If there's a single column, set it
        if isinstance(self.name_list, str):
            return OrderedDict([(self.name_list, res)])
        else:
            d = OrderedDict()
            #Unpack the values
            for i in xrange(len(self.name_list)):
                d[self.name_list[i]] = res[i]
            return d

    def summarize(self, data):
        '''Summarize the data for the columns described in this pack'''
        name_list = self.name_list
        #If there's a single column
        if isinstance(name_list, str):
            name_list = [name_list]
        d = OrderedDict()
        #For each column
        for name in name_list:
            #Get the total
            d[name] = self.total_func_dict[name](data[name])
        return d

    def format(self, row):
        '''Format the given row (in place) for the columns described in this pack.'''
        if self.format_dict is None:
            return
        #If this is a single column
        if isinstance(self.name_list, str):
            #If the formatter exists
            if self.format_dict[self.name_list] is None:
                return
            #Apply the formatter to the column
            row[self.name_list] = self.format_dict[self.name_list](row[self.name_list])
        else:
            #For each column
            for name in self.name_list:
                #If the formatter exists
                if self.format_dict[name] is None:
                    continue
                #Apply the formatter to the column
                row[name] = self.format_dict[name](row[name])

#Default columns
#Getters for the columns
def calc_energy(reebill, service, reebill_ub, mub, ub):
    '''Calculate the renewable and conventional energy usage for a reebill'''
    def normalize(units, total):
        if (units.lower() == "kwh"):
            # 1 kWh = 3413 BTU
            return total * 3413
        elif (units.lower() == "therms" or units.lower() == "ccf"):
            # 1 therm = 100000 BTUs
            return total * 100000
        else:
            raise Exception("Units '" + units + "' not supported")
    re = 0.0
    ce = 0.0
    for meter in reebill.meters[service]:
        for register in meter['registers']:
            units = register['quantity_units']
            total = float(register['quantity'])
            #Shadow registers are renewable, normal are conventional
            if register['shadow'] == True:
                re += normalize(units, total)
            else:
                ce += normalize(units, total)
    return (ce, re)

get_start_date = lambda r, s, rub, mub, ub: (ub.period_start)
get_end_date = lambda r, s, rub, mub, ub: (ub.period_end)
get_util_charges = lambda r, s, rub, mub, ub: (float(rub['hypothetical_total'])-float(rub['ree_value']))
get_ree_value = lambda r, s, rub, mub, ub: (float(rub['ree_value']))
get_ree_charges = lambda r, s, rub, mub, ub: (float(rub['ree_charges']))

#Format the start and end dates as mm/dd/yy
format_date = lambda d: d.strftime('%m/%d/%y')

start_date_column = ColumnPack('Start Date', get_start_date, min, formatters = format_date)
end_date_column = ColumnPack('End Date', get_end_date, max, formatters = format_date)
energy_columns = ColumnPack(('Utility BTUs', 'REE BTUs'), calc_energy, (sum, sum))
util_charges_column = ColumnPack('Utility Charges', get_util_charges, sum)
ree_value_column = ColumnPack('REE Value', get_ree_value, sum)
ree_charges_column = ColumnPack('REE Charges', get_ree_charges, sum)
default_columns = [start_date_column, end_date_column, energy_columns, util_charges_column, ree_value_column, ree_charges_column]

def months_contained(start_date, end_date):
    '''Returns a list of dates(y, m, 1) for months that intersect the given period.  The period does not include end_date'''
    start_month = start_date.month
    start_year = start_date.year
    end_month = end_date.month%12 + 1 if end_date.day != 1 else end_date.month
    end_year = end_date.year + (1 if end_month == 1 and end_date.day != 1 else 0)
    month_dates = [date(end_year+((month-1)/12), ((month-1)%12)+1, 1) for month in range(start_month-(end_year-start_year)*12,end_month+1)]
    return month_dates

def approximate_months(start_date, end_date):
    '''
    Determine what months the given period falls in and how close it matches each month
    
        Returns a list [(date(y,m,1), days in month and in period, fraction of month in period, fraction of period in month]
    '''
    total_days = (end_date - start_date).days
    month_dates = months_contained(start_date, end_date)
    days_per_month = [(month_dates[i+1]-month_dates[i]).days for i in range(len(month_dates)-1)]
    days_in_months = [(min(month_dates[i+1], end_date)-max(month_dates[i], start_date)).days for i in range(len(month_dates)-1)]
    fractions_of_months = [float(days_in_months[i])/float(days_per_month[i]) for i in range(len(days_in_months))]
    fraction_of_total = [float(days_in_months[i])/float(total_days) for i in range(len(days_in_months))]
    return [(month_dates[i], days_in_months[i], fractions_of_months[i], fraction_of_total[i]) for i in range(len(days_in_months))]

def is_set(month_dict, month):
    '''Determines if the given month has already had a utility bill assigned to it'''
    return any([_ub[1] for _ub in month_dict.get(month,[])])

def set_month_to_utilbill(month_dict, ub_dict, month, utilbill):
    '''
    Assign a utility bill to a month
    '''
    already_exists = is_set(month_dict[utilbill.service], month)
    #Print an error if tryint to assign to an already taken month
    if already_exists:
        print "  Multiple utility bills for "+month.strftime('%b %Y')
        for ub_id in month_dict[utilbill.service][month]:
            print "    "+str(ub_dict[ub_id[0]][0])
        print "    "+str(ub_dict[utilbill.id][0])
        return False
    else:
        #Assign the utilbill to the month
        old_ubs = month_dict[utilbill.service][month]
        old_months = ub_dict[utilbill.id][1]
        #Clear this utilbill from any months it previously belonged to
        for entry in old_months:
            if entry == month:
                continue
            if is_set(month_dict[utilbill.service], entry):
                print "  Utility Bill "+str(utilbill)+" is already applied to "+entry.strftime('%b %Y')
                print "    Attempted "+month.strftime('%b, %Y')
                return False
            else:
                month_dict[utilbill.service][entry] = [tup for tup in month_dict[utilbill.service][entry] if tup[0] != utilbill.id]
        month_dict[utilbill.service][month] = [(utilbill.id, True)]
        ub_dict[utilbill.id][1] = [month]
        success = True
        #Go through all the utilbills that were there before and see if they need to be assigned
        for entry in old_ubs:
            ub_id = entry[0]
            if ub_id == utilbill.id:
                continue
            ub_dict[ub_id][1].remove(month)
            #If there's only one possibility left, assign to it
            if len(ub_dict[ub_id][1]) == 1:
                success = success and set_month_to_utilbill(month_dict, ub_dict, ub_dict[ub_id][1][0], ub_dict[ub_id][0])
        return success

def get_column_names(columns):
    '''Get the names for all the columns described'''
    names = []
    for col in columns:
        #If there's only one, add it to the list
        if isinstance(col.name_list, str):
            names.append(col.name_list)
        else:
            #Add all of them to the list
            names.extend(col.name_list)
    return names

def get_stats(reebill, utilbill, columns):
    '''Get the given statistics for this reebill'''
    service = utilbill.service
    reebill_ub = reebill._get_handle_for_service(service)
    ub = reebill._get_utilbill_for_handle(reebill_ub)
    data = OrderedDict()
    for col in columns:
        data.update(col.get_stats(reebill, service, reebill_ub, ub, utilbill))
    return data

def summarize(columns, column_data):
    '''Summarize the data for a set of columns'''
    totals = OrderedDict()
    for col in columns:
        totals.update(col.summarize(column_data))
    return totals

def format_row(columns, row):
    '''Format the given row containing the given columns'''
    for col in columns:
        col.format(row)
                
class Exporter:
    def __init__(self, host, mongodb, statedb, user, password):
        '''Initalize the databases to be used'''
        self.state_db = state.StateDB(host, statedb, user, password)
        self.reebill_dao = mongo.ReebillDAO(self.state_db, host, database = mongodb)

    def export_with_month(self, output_file_name, accounts = None, start_date = None, end_date = None, threshold = 0.8, columns = default_columns):
        '''
        Export reebill data to a file

        accounts is either a list of accounts or None for all accounts
        output_file_name is any file ending in .xls, .json, .yaml or .ods
        columns is a list of ColumnPacks wanted in the output.  The 'Month' and 'Service' columns are always there
          The default columns are:
          Start Date
          End Date
          Utility BTUs
          REE BTUs
          Utility Charges
          REE Value
          REE Charges
        The start_date and end_date must be the beginning of months or None; both of these months are included
        A start_date of None includes everything since the beginning till the end_date
        An end_date of None includes everything until the end since the start_date
        threshold determines how tightly a reebill must be coupled to a month to be assigned to it.  0.8 seems to work well
        '''
        file_extension = os.path.splitext(output_file_name)[1][1:]
        if file_extension not in ['xls', 'json', 'yaml', 'ods']:
            print "Allowed extensions: .xls, .json, .yaml, .ods"
            raise ValueError("Unrecognized extension: "+file_extension)

        if (start_date is not None and start_date.day != 1) or (end_date is not None and end_date.day != 1):
            raise ValueError("Both start and end date must be the beginnings of months")
        
        #output databook
        book = tablib.Databook()
        with DBSession(self.state_db) as session:
            if accounts is None:
                accounts = self.state_db.listAccounts(session)

            for account in accounts:
                try:
                    print "Generating sheet for account " + account
                    #sheet for this account
                    sheet = tablib.Dataset(title=account)
                    sheet.headers = ['Month', 'Service']
                    sheet.headers.extend(get_column_names(columns))
                    matching_utilbills, first_date, last_date = self.state_db.list_issued_utilbills_for_account(session, account)
                    #skip the account if it has no utilbills
                    if len(matching_utilbills) == 0:
                        print "  No utility bills found"
                        print
                        continue
                    services = list({ub.service.lower() if ub.service is not None else 'unknown' for ub in matching_utilbills})
                    #if start date is none, get all months starting at the first utilbill.
                    #if end date is none, get all months up to the end of the last utilbill
                    months_wanted = months_contained(start_date if start_date else first_date, end_date if end_date else last_date)
                    #{service: {month: [(utilbill_id, is_assigned), ...]}}
                    all_months = {service: OrderedDict([(month, []) for month in months_contained(first_date, last_date)]) for service in services}
                    #{utilbill_id: [utilbill_doc, [months added]]}
                    ubs = {}
                    for ub in matching_utilbills:
                        ub.service = ub.service.lower() if ub.service is not None else 'unknown'
                        ubs[ub.id] = [ub, []]
                        #Figure out which months this bill belongs to
                        month_stats = approximate_months(ub.period_start, ub.period_end)
                        #Figure out which aren't already taken
                        months = [month for month in month_stats if not is_set(all_months[ub.service], month[0])]
                        #Figure out which months this utilbill both contains most of and is mostly contained by
                        matching_months = [month[0] for month in months if month[2] >= threshold and month[3] >= threshold]
                        #If it matches only one, assign the utilbill to that month
                        if len(matching_months) == 1:
                            set_month_to_utilbill(all_months, ubs, matching_months[0], ub)
                        elif len(months) == 1:
                            set_month_to_utilbill(all_months, ubs, months[0][0], ub)
                        #If it matches some untaken months, add it to those months (but don't assign it)
                        elif len(months) > 1:
                            for month in months:
                                all_months[ub.service][month[0]].append((ub.id, False))
                                ubs[ub.id][1].append(month[0])
                        #If there were some matches but they were taken
                        elif len(month_stats) > 0:
                            print "  All months already taken for utility bill:"
                            print "    "+str(ub)
                            print "  Possible:"
                            for month in month_stats:
                                print "    "+month[0].strftime('%b %Y')
                        else:
                            print "Error: no month found for utility bill:"
                            print "    "+str(ub)
                    #Go through all utility bills and pick the month that they fit best
                    for ub, month_list in ubs.itervalues():
                        if len(month_list) > 1:
                            month_stats = approximate_months(ub.period_start, ub.period_end)
                            #Get the available months
                            months_available = [stats for stats in month_stats if not is_set(all_months, stats[0])]
                            #Sort by match
                            months_available.sort(key=lambda s:(s[2] + s[3]), reverse = True)
                            #Pick the best one
                            month = months_available[0]
                            set_month_to_utilbill(all_months, ubs, month[0], ub)
                    #Get the wanted utilbill ids, determined by those where a wanted month points to them
                    ubs_wanted = [ub_id for ub_id in ubs.iterkeys() if any([any([any([ub_id_ok[0]==ub_id for ub_id_ok in ub_list]) for month, ub_list in month_dict.iteritems() if month in months_wanted]) for month_dict in all_months.itervalues()])]
                    #If there were no matching utility bills for this account
                    if len(ubs_wanted) == 0:
                        print "  No utility bills matched the months given"
                        print
                        continue
                    total = OrderedDict()
                    all_time = OrderedDict()
                    rows = OrderedDict()
                    ubs_found = []
                    #month_list = {month: [(utilbill_id, is_assigned), ...]}
                    for service, month_list in all_months.iteritems():
                        first = True
                        missing = []
                        #ub_list = [(utilbill_id, is_assigned), ...]
                        #There should only be one utilbill in that list
                        for month, ub_list in month_list.iteritems():
                            #Mark that each of these utilbills was found
                            if not is_set(month_list, month) and len(ub_list) > 0:
                                print "  No utilbill set for "+month.strftime('%b %Y')
                                print "  Available: "
                                for ub_id in ub_list:
                                    print "    "+str(ubs[ub_id[0]][0])
                                continue
                            for ub_id in ub_list:
                                ubs_found.append(ub_id[0])
                            #Don't continue adding to the totals if the month of the bill is past the end date
                            if month > (end_date if end_date else last_date):
                                continue
                            #If this month has no associated utilbill
                            if not first and len(ub_list) == 0:
                                missing.append(month)
                            #If this month has more than one utilbill
                            elif len(ub_list) > 1:
                                print "  "+m.strftime('%b %Y')+" has multiple possibilities"
                            elif len(ub_list) == 1:
                                #Get the matching utilbill document using the id
                                ub_id = ub_list[0][0]
                                utilbill = ubs[ub_id][0]
                                #Start checking for missing months
                                if first:
                                    first = False
                                #Flush missing months and reset it
                                else:
                                    for m in missing:
                                        print "  Missing "+m.strftime('%b %Y')
                                    missing = []
                                #Get the reebill document from mongo
                                reebill = self.reebill_dao.load_reebill(account, utilbill.sequence)
                                stats = get_stats(reebill, utilbill, columns)
                                if ub_id in ubs_wanted:
                                    #Check if the total for this service has started accumulating
                                    if service not in total:
                                        total[service] = OrderedDict()
                                        for name in get_column_names(columns):
                                            total[service][name] = [stats[name]]
                                    else:
                                        for name in get_column_names(columns):
                                            total[service][name].append(stats[name])
                                    #Add this row to the list
                                    if month not in rows:
                                        rows[month] = OrderedDict()
                                    rows[month][service] = stats
                                if service not in all_time:
                                    #Check if the all time total for this service has started accumulating
                                    all_time[service] = OrderedDict()
                                    for name in get_column_names(columns):
                                        all_time[service][name] = [stats[name]]
                                else:
                                    for name in get_column_names(columns):
                                        all_time[service][name].append(stats[name])
                    #Check that all utilbills are accounted for
                    ubs_missing = [ubs[ub_id][0] for ub_id in ubs.iterkeys() if ub_id not in ubs_found]
                    for ub in ubs_missing:
                        print "  Utilbill "+str(ub)+" not accounted for"
                    
                    #Add the accumulated rows in the crrect order
                    for month, row_dict in rows.iteritems():
                        for service, row in row_dict.iteritems():
                            format_row(columns, row)
                            lrow = [month.strftime('%b %Y'), service]
                            lrow.extend(row.values())
                            sheet.append(lrow)
    
                    for service, column_data in total.iteritems():
                        totals = summarize(columns, column_data)
                        format_row(columns, totals)
                        row = ['Total', service]
                        row.extend(totals.values())
                        sheet.append(row)
                        
                    for service, column_data in all_time.iteritems():
                        totals = summarize(columns, column_data)
                        format_row(columns, totals)
                        row = ['All Time', service]
                        row.extend(totals.values())
                        sheet.append(row)
                    
                    book.add_sheet(sheet)
                except:
                    print "  "+traceback.format_exc().replace('\n','\n  ')[:-3]
                print

        with open(output_file_name, 'wb') as output_file:
            if (file_extension == 'json'):
                output_file.write(book.json)
            elif (file_extension == 'xls'):
                output_file.write(book.xls)
            elif (file_extension == 'yaml'):
                output_file.write(book.yaml)
            elif (file_extension == 'ods'):
                output_file.write(book.ods)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Export Reebill data for a set of accounts over a period of months', formatter_class = argparse.RawTextHelpFormatter)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-a', '--accounts', nargs = '+', metavar = ('NAME', 'NAMES'), help = "List of accounts to process (Default: all)")
    parser.add_argument('-s', '--start', type=int, metavar = ('MM', 'YYYY'), nargs = 2, help = "Start month (Default: beginning of time)")
    parser.add_argument('-e', '--end', type=int, metavar = ('MM', 'YYYY'), nargs = 2, help = "End month (Default: end of time)")
    parser.add_argument('-o', '--output-file', default = 'output.xls', metavar = 'FILE', help = "Output file (type determined by extension")
    parser.add_argument('-t', '--host', default = 'localhost', metavar = 'HOST', help = "Database host")
    parser.add_argument('-m', '--mongodb', default = 'skyline-dev', metavar = 'NAME', help = "Name of mongo database")
    parser.add_argument('-d', '--statedb', default = 'skyline_dev', metavar = 'NAME', help = "Name of mysql database")
    parser.add_argument('-u', '--user', default = ['dev', 'dev'], nargs = 2, metavar = ('USER', 'PASS'), help = "Username and password for mysql database")
    parser.add_argument('-r', '--threshold', type = float, default = 80., metavar = 'THRESH', help = "The %% of a bill required to be in a month to apply that bill to that month")
    args = parser.parse_args()
    
    accounts = args.accounts
    output_file_name = args.output_file
    #Start Date of none means since the beginning
    start_date = None
    if args.start is not None:
        start_month = args.start[0]
        start_year = args.start[1]
        start_date = date(start_year, start_month, 1)
    #End Date of none means until the end
    end_date = None
    if args.end is not None:
        end_month = args.end[0]
        end_year = args.end[1]
        end_date = date(end_year, end_month, 1)
    
    host = args.host
    db = args.mongodb
    statedb = args.statedb
    user = args.user[0]
    password = args.user[1]
    
    threshold = args.threshold / 100.
    
    exporter = Exporter(host, db, statedb, user, password)
    exporter.export_with_month(output_file_name, accounts, start_date, end_date, threshold)
    
