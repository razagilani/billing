"""Upgrade script for version 27.

Script must define `upgrade`, the function for upgrading.

Important: For the purpose of allowing schema migration, this module will be
imported with the data model uninitialized! Therefore this module should not
import any other code that that expects an initialized data model without first
calling :func:`.core.init_model`.
"""
import logging
from core.extraction.extraction import TextExtractor, Field, Applier, Extractor, \
    LayoutExtractor, BoundingBox
from core.model import Utility

from upgrade_scripts import alembic_upgrade
from core import init_model, initialize, init_config

log = logging.getLogger(__name__)

def create_extractors(s):
    date_format = r'[A-Za-z]+\s*[0-9]{1,2},\s*[0-9]{4}'
    num_format = r'[0-9,\.]+'
    zip_code_format = r'\d{5}-\d{4}' #used to delimit addresses in bills
    start_regex = 'Your electric bill - [A-Za-z]+ [0-9]{4}for the period (%s)' % date_format
    end_regex = 'Your electric bill - [A-Za-z]+ [0-9]{4}for the period %s to (%s)' % (date_format, date_format)
    energy_regex = r'.*([0-9]{4})Your next meter'
    next_meter_read_regex = r'.*Your next meter reading is scheduled for (%s)' % date_format
    e =  TextExtractor(name='Original Pepco Extractor')
    e.fields.append(TextExtractor.TextField(regex=start_regex, type=Field.DATE, applier_key=Applier.START))
    e.fields.append(TextExtractor.TextField(regex=end_regex, type=Field.DATE, applier_key=Applier.END))
    e.fields.append(TextExtractor.TextField(regex=energy_regex, type=Field.FLOAT, applier_key=Applier.ENERGY))
    e.fields.append(TextExtractor.TextField(regex=next_meter_read_regex, type=Field.DATE, applier_key=Applier.NEXT_READ))

    #pepco bills from 2015, with banner
    pep_start_regex = 'your electric bill for the period\s*(%s) to %s' % (date_format, date_format)
    pep_end_regex = 'your electric bill for the period\s*%s to (%s)' % (date_format, date_format)
    pep_energy_regex = r'Use \(kWh\)\s+(%s)' % num_format
    pep_next_meter_read_regex = r'Your next meter reading is scheduled for (%s)' % date_format
    pep_charges_regex = r'(Distribution Services:.*?(?:Status of your Deferred|Page)(?:.*?)Transmission Services\:.*?Energy Usage History)'
    pep_service_address_regex = r'service address:\s*(.*?)Bill Issue'
    pep_billing_address_regex = r'\d{8} \d{9}(.*?%s)' % zip_code_format
    pep_rate_class_regex = r'Details of your electric charges(.*?)\s+-\s+service number'
    pepco_2015 = TextExtractor(name="Extractor for Pepco bills in 2015 id 18541")
    pepco_2015.fields.append(TextExtractor.TextField(regex=pep_start_regex, type=Field.DATE, applier_key=Applier.START))
    pepco_2015.fields.append(TextExtractor.TextField(regex=pep_end_regex, type=Field.DATE, applier_key=Applier.END))
    pepco_2015.fields.append(TextExtractor.TextField(regex=pep_energy_regex, type=Field.FLOAT, applier_key=Applier.ENERGY))
    pepco_2015.fields.append(TextExtractor.TextField(regex=pep_next_meter_read_regex, type=Field.DATE, applier_key=Applier.NEXT_READ))
    pepco_2015.fields.append(TextExtractor.TextField(regex=pep_charges_regex, type=Field.PEPCO_NEW_CHARGES, applier_key=Applier.CHARGES))
    pepco_2015.fields.append(TextExtractor.TextField(regex=pep_service_address_regex, type=Field.ADDRESS, applier_key=Applier.SERVICE_ADDRESS))
    pepco_2015.fields.append(TextExtractor.TextField(regex=pep_billing_address_regex, type=Field.ADDRESS, applier_key=Applier.BILLING_ADDRESS))
    pepco_2015.fields.append(TextExtractor.TextField(regex=pep_rate_class_regex, type=Field.STRING, applier_key=Applier.RATE_CLASS))

    #pepco bills from before 2015, blue logo
    pep_old_start_regex = r'Services for (%s) to %s' % (date_format, date_format)
    pep_old_end_regex = r'Services for %s to (%s)' % (date_format, date_format)
    pep_old_energy_regex = r'KWH\s*Used\s+(\d+)'
    pep_old_next_meter_read_regex = r'.Your next scheduled meter reading is (%s)' % date_format
    pep_old_charges_regex = r'(distribution services.*?current charges this period)'
    pep_old_service_address_regex = r'Service Address:\s+(.*?)\n\n'
    pep_old_billing_address_regex = r'\n\n((?:[^\n]|\n(?!\n))+%s)\n\nPepco Telephone Contacts:' % zip_code_format
    pep_old_rate_class_regex = r'Meter Reading Information[A-Z0-9]*\s+(.*)The present reading'
    pepco_old = TextExtractor(name='Pepco bills from before 2015 with blue logo id 2631')
    pepco_old.fields.append(TextExtractor.TextField(regex=pep_old_start_regex, type=Field.DATE, applier_key=Applier.START))
    pepco_old.fields.append(TextExtractor.TextField(regex=pep_old_end_regex, type=Field.DATE, applier_key=Applier.END))
    pepco_old.fields.append(TextExtractor.TextField(regex=pep_old_energy_regex, type=Field.FLOAT, applier_key=Applier.ENERGY))
    pepco_old.fields.append(TextExtractor.TextField(regex=pep_old_next_meter_read_regex, type=Field.DATE, applier_key=Applier.NEXT_READ))
    pepco_old.fields.append(TextExtractor.TextField(regex=pep_old_charges_regex, type=Field.PEPCO_OLD_CHARGES, applier_key=Applier.CHARGES))
    pepco_old.fields.append(TextExtractor.TextField(regex=pep_old_service_address_regex, type=Field.ADDRESS, applier_key=Applier.SERVICE_ADDRESS))
    pepco_old.fields.append(TextExtractor.TextField(regex=pep_old_billing_address_regex, type=Field.ADDRESS, applier_key=Applier.BILLING_ADDRESS))
    pepco_old.fields.append(TextExtractor.TextField(regex=pep_old_rate_class_regex, type=Field.STRING, applier_key=Applier.RATE_CLASS))

    #washington gas bills
    wg_start_regex = r'(%s)-%s\s*\(\d+ Days\)' % (date_format, date_format)
    wg_end_regex = r'%s-(%s)\s*\(\d+ Days\)' % (date_format, date_format)
    wg_energy_regex = r"Distribution Charge\s+(%s)" % num_format
    wg_next_meter_read_regex = r'Your next meter reading date is (%s)' % date_format
    wg_charges_regex = r'(DISTRIBUTION SERVICE.*?(?:Total Washington Gas Charges This Period|the easiest way to pay))'
    wg_service_address_regex = r'(?:Days\)|Service address:)\s+(.+?)\s+(?:Questions|Please)'
    #for billing address, before "check here to donate", get all characters that are not a double newline
    wg_billing_address_regex=r'\n\n([^\n]|\n(?!\n))*\n\nCheck here to donate'
    wg_rate_class_regex = r'rate class:\s+meter number:\s+([^\n]+)'
    washington_gas = TextExtractor(name='Extractor for Washington Gas bills '
                                        'with green and yellow and chart ('
                                        'after 2014) id 15311')
    washington_gas.fields.append(TextExtractor.TextField(regex=wg_start_regex, type=Field.DATE, applier_key=Applier.START))
    washington_gas.fields.append(TextExtractor.TextField(regex=wg_end_regex, type=Field.DATE, applier_key=Applier.END))
    washington_gas.fields.append(TextExtractor.TextField(regex=wg_energy_regex, type=Field.FLOAT, applier_key=Applier.ENERGY))
    washington_gas.fields.append(TextExtractor.TextField(regex=wg_next_meter_read_regex, type=Field.DATE, applier_key=Applier.NEXT_READ))
    washington_gas.fields.append(TextExtractor.TextField(regex=wg_charges_regex, type=Field.WG_CHARGES, applier_key=Applier.CHARGES))
    washington_gas.fields.append(TextExtractor.TextField(regex=wg_service_address_regex, type=Field.ADDRESS, applier_key=Applier.SERVICE_ADDRESS))
    washington_gas.fields.append(TextExtractor.TextField(regex=wg_billing_address_regex, type=Field.ADDRESS, applier_key=Applier.BILLING_ADDRESS))
    washington_gas.fields.append(TextExtractor.TextField(
        regex=wg_rate_class_regex, type=Field.STRING, applier_key=Applier.RATE_CLASS))

    wg_layout_period_regex = r"Period:\s+(%s)-%s" % (date_format, date_format)
    wg_layout_next_read_regex = r"Your next meter reading date is %s" % date_format
    washington_gas_layout = LayoutExtractor(name='Layout Extractor for '
                                                 'Washington Gas bills with '
                                                 'green and yellow and chart '
                                                 '(after 2014) id 15311')
    washington_gas_layout.fields.append(LayoutExtractor.BoundingBoxField(
        regex=wg_layout_period_regex, page_num=1,
        bbminx=411, bbminy=712, bbmaxx=441, bbmaxy=717,
        type=Field.DATE,
        applier_key=Applier.START))
    washington_gas_layout.fields.append(LayoutExtractor.BoundingBoxField(
        regex=wg_layout_period_regex, page_num=1,
        bbminx=411, bbminy=712, bbmaxx=441, bbmaxy=717,
        type=Field.DATE,
        applier_key=Applier.END))
    washington_gas_layout.fields.append(LayoutExtractor.BoundingBoxField(
        regex=wg_layout_next_read_regex, page_num=1,
        bbminx=32, bbminy=571, bbmaxx=223, bbmaxy=588,
        type=Field.DATE,
        applier_key=Applier.NEXT_READ))
    washington_gas_layout.fields.append(LayoutExtractor.BoundingBoxField(
        regex=r"(.*)Service address:\s+(.*)\s?$", page_num=1,
        bbminx=411, bbminy=690, bbmaxx=480, bbmaxy=706,
        type=Field.ADDRESS,
        applier_key=Applier.SERVICE_ADDRESS))
    washington_gas_layout.fields.append(LayoutExtractor.BoundingBoxField(
        regex=r"", page_num=1,
        bbminx=66, bbminy=61, bbmaxx=203, bbmaxy=91,
        type=Field.ADDRESS,
        applier_key=Applier.BILLING_ADDRESS))
    washington_gas_layout.fields.append(LayoutExtractor.BoundingBoxField(
        regex=r"Rate Class:\s+(.*)\s?$", page_num=2,
        bbminx=39, bbminy=715, bbmaxx=105, bbmaxy=725,
        type=Field.STRING,
        applier_key=Applier.RATE_CLASS))
    s.add_all([e, pepco_2015, pepco_old, washington_gas, washington_gas_layout])

def create_charge_name_maps(s):
    wg = s.query(Utility).filter_by(name='washington gas').one()
    wg.charge_name_map = {
            'Distribution Charge': 'DISTRIBUTION_CHARGE',
            'Customer Charge': 'CUSTOMER_CHARGE',
            'PGC': 'PGC',
            'Peak Usage Charge': 'PEAK_USAGE_CHARGE',
            'DC Rights-of-Way Fee': 'RIGHT_OF_WAY',
            'Sustainable Energy Trust Fund': 'SETF',
            'Energy Assistance Trust Fund': 'EATF',
            'Delivery Tax': 'DELIVERY_TAX',
            'Sales Tax': 'SALES_TAX',
        }

    pepco = s.query(Utility).filter_by(name='pepco').one()
    pepco.charge_name_map = {
        'Customer Charge':'CUSTOMER_CHARGE',
        'Energy Charge':'ENERGY_CHARGE',
        'Grid Resiliency Charge':'GRID_RESILIENCY_CHARGE',
        'Franchise Tax (Delivery)':'DELIVERY_TAX',
        'Universal Service Charge':'UNIVERSAL_SERVICE_CHARGE',
        'Gross Receipts Tax':'GROSS_RECEIPTS_TAX',
    }

    # TODO: add charge_name_map's for other utilities

def upgrade():
    # initialize()
    # from core.model import Base, Session
    # s = Session()
    # s.execute('drop type if exists field_type')
    # Field.__table__.drop(Session.bind, checkfirst=True)
    # Extractor.__table__.drop(Session.bind, checkfirst=True)
    # Base.metadata.drop_all()
    # Base.metadata.create_all()
    alembic_upgrade('30597f9f53b9')

    initialize()
    from core.model import Base, Session
    print '\n'.join(sorted(t for t in Base.metadata.tables))
    s = Session()


    # s.query(Field).delete()
    # s.query(Extractor).delete()
    # hstore won't work unless it's specifically turned on
    s.execute('create extension if not exists hstore')
    s.commit()
    create_extractors(s)
    create_charge_name_maps(s)
    s.commit()

