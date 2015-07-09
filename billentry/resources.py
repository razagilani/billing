"""REST resource classes for the UI of the Bill Entry application.
"""
from datetime import datetime
import os

from dateutil import parser as dateutil_parser
from boto.s3.connection import S3Connection
from flask import session
from flask.ext.login import current_user, logout_user
from flask.ext.principal import Permission, RoleNeed
from flask.ext.restful import Resource, marshal, abort
from flask.ext.restful.fields import Raw, String, Integer, Float, Boolean,\
    List
from flask.ext.restful.reqparse import RequestParser
from sqlalchemy import desc, and_, func, case, cast, Integer as integer
from sqlalchemy.orm import joinedload
from sqlalchemy.orm.exc import NoResultFound
import werkzeug

from billentry.billentry_model import BEUtilBill, BEUserSession
from billentry.billentry_model import BillEntryUser
from billentry.common import replace_utilbill_with_beutilbill
from billentry.common import account_has_bills_for_data_entry
from brokerage.brokerage_model import BrokerageAccount
from core.altitude import AltitudeAccount, update_altitude_account_guids
from core.bill_file_handler import BillFileHandler
from core.model import Session, UtilBill, Supplier, Utility, RateClass, Charge, SupplyGroup, Address
from core.model import UtilityAccount
from core.pricing import FuzzyPricingModel
from core.utilbill_loader import UtilBillLoader
from core.utilbill_processor import UtilbillProcessor
from exc import MissingFileError


project_mgr_permission = Permission(RoleNeed('Project Manager'),
                                    RoleNeed('admin'))

admin_permission = Permission(RoleNeed('admin'))


# TODO: would be even better to make flask-restful automatically call any
# callable attribute, because no callable attributes will be normally
# formattable things like strings/numbers anyway.
class CallableField(Raw):
    '''Field type that wraps another field type: it calls the attribute,
    then formats the return value with the other field.
    '''
    def __init__(self, result_field, *args, **kwargs):
        '''
        :param result_field: field instance (not class) to format the result of
        calling the attribute.
        '''
        super(CallableField, self).__init__(*args, **kwargs)
        assert isinstance(result_field, Raw)
        self.result_field = result_field

    def format(self, value):
        value = value()
        if value is None:
            # 'default' comes from a kwarg to Raw.__init__
            return self.default
        return self.result_field.format(value)


class CapString(String):
    '''Like String, but first letter is capitalized.'''
    def format(self, value):
        return value.capitalize()


class IsoDatetime(Raw):
    def format(self, value):
        if value is None:
            return None
        return value.isoformat()


class BaseResource(Resource):
    '''Base class of all resources. Contains UtilbillProcessor object to be
    used in handling requests, and shared code related to JSON formatting.
    '''
    def __init__(self):
        from core import config
        s3_connection = S3Connection(
            config.get('aws_s3', 'aws_access_key_id'),
            config.get('aws_s3', 'aws_secret_access_key'),
            is_secure=config.get('aws_s3', 'is_secure'),
            port=config.get('aws_s3', 'port'),
            host=config.get('aws_s3', 'host'),
            calling_format=config.get('aws_s3', 'calling_format'))
        utilbill_loader = UtilBillLoader()
        # TODO: ugly. maybe put entire url_format in config file.
        url_format = '%s://%s:%s/%%(bucket_name)s/%%(key_name)s' % (
            'https' if config.get('aws_s3', 'is_secure') is True else
            'http', config.get('aws_s3', 'host'),
            config.get('aws_s3', 'port'))
        bill_file_handler = BillFileHandler(
            s3_connection, config.get('aws_s3', 'bucket'),
            utilbill_loader, url_format)
        pricing_model = FuzzyPricingModel(utilbill_loader)
        self.utilbill_processor = UtilbillProcessor(
            pricing_model, bill_file_handler, None)

        # field for getting the URL of the PDF corresponding to a UtilBill:
        # requires BillFileHandler, so not an attribute of UtilBill itself
        class PDFUrlField(Raw):
            def output(self, key, obj):
                return bill_file_handler.get_url(obj)

        class WikiUrlField(Raw):
            def output(self, key, obj):
                return config.get('billentry',
                                  'wiki_url') + obj.get_utility_name()

        # TODO: see if these JSON formatters can be moved to classes that
        # only deal with the relevant objects (UtilBills or Charges). they're
        # here because there's more than one Resource that needs to use each
        # one (representing individual UtilBills/Charges and lists of them).
        self.utilbill_fields = {
            'id': Integer,
            'utility_account_id': Integer,
            'period_start': IsoDatetime,
            'period_end': IsoDatetime,
            'service': CallableField(
                CapString(), attribute='get_service', default='Unknown'),
            'total_energy': CallableField(Float(),
                                          attribute='get_total_energy'),
            'target_total': Float(attribute='target_total'),
            'computed_total': CallableField(Float(),
                                            attribute='get_total_charges'),
            # TODO: should these be names or ids or objects?
            'utility': CallableField(String(), attribute='get_utility_name'),
            'utility_id': CallableField(Integer(), attribute='get_utility_id'),
            'supplier': CallableField(String(), attribute='get_supplier',
                                      default='Unknown'),
            'supplier_id': CallableField(Integer(), attribute='get_supplier_id',
                                         default=None),
            'rate_class': CallableField(
                String(), attribute='get_rate_class_name', default='Unknown'),
            'rate_class_id': CallableField(Integer(), attribute='get_rate_class_id'),
            'supply_group': CallableField(
                String(), attribute='get_supply_group_name', default='Unknown'),
            'supply_group_id': CallableField(
                Integer(), attribute='get_supply_group_id', default=None),
            'pdf_url': PDFUrlField,
            'service_address': String,
            'next_meter_read_date': CallableField(
                IsoDatetime(), attribute='get_next_meter_read_date',
                default=None),
            'supply_total': CallableField(Float(),
                                          attribute='get_supply_target_total'),
            'utility_account_number': CallableField(
                String(), attribute='get_utility_account_number'),
            'entered': CallableField(Boolean(), attribute='is_entered'),
            'supply_choice_id': String,
            'processed': Boolean,
            'flagged': CallableField(Boolean(), attribute='is_flagged'),
            'due_date': IsoDatetime,
            'wiki_url': WikiUrlField, 'tou': Boolean,
            'meter_identifier': CallableField(
                String(), attribute='get_total_meter_identifier')
        }

        self.charge_fields = {
            'id': Integer,
            'rsi_binding': String,
            'target_total': Float,
        }

        self.supply_group_fields = {
            'id': Integer,
            'name': String,
            'supplier_id': Integer,
            'service': String
        }

        self.utility_fields = {
            'id': Integer,
            'name': String,
            'sos_supply_group_id': String
        }

        self.altitude_account_fields = {
            'utility_account_id': Integer,
            'guid': String
        }

# basic RequestParser to be extended with more arguments by each
# put/post/delete method below.
id_parser = RequestParser()
id_parser.add_argument('id', type=int, required=True)

# TODO: determine when argument to put/post/delete methods are created
# instead of RequestParser arguments


# A callable to parse a string into a Date() object via dateutil.
# This is declared globally for reuse as a type keyword in calls to
# RequestParser.add_argument() in many of the Resources below
parse_date = lambda _s: dateutil_parser.parse(_s).date()


class AccountListResource(BaseResource):
    def get(self):
        accounts = Session().query(UtilityAccount).join(
            BrokerageAccount).options(joinedload('utilbills')).options(
            joinedload('fb_utility')).order_by(UtilityAccount.account).all()
        return [dict(marshal(account, {
            'id': Integer,
            'account': String,
            'utility_account_number': String(attribute='account_number'),
            'utility': String(attribute='fb_utility'),
            'service_address': CallableField(String(),
                attribute='get_service_address'),
            }),bills_to_be_entered=account_has_bills_for_data_entry(
                         account)) for account in accounts]


class AccountResource(BaseResource):

    def put(self, id):
        account = Session().query(UtilityAccount).filter_by(id=id).one()
        return dict(marshal(account, {
            'id': Integer,
            'account': String,
            'utility_account_number': String(attribute='account_number'),
            'utility': String(attribute='fb_utility'),
            'service_address': CallableField(String(),
                                             attribute='get_service_address'),
        }), bills_to_be_entered=account_has_bills_for_data_entry(account))


class AltitudeAccountResource(BaseResource):

    def get(self):
        altitude_accounts = Session.query(AltitudeAccount).all()
        accounts = [marshal(altitude_account, self.altitude_account_fields)
            for altitude_account in altitude_accounts]
        return {'rows': accounts, 'results': len(accounts)}


class UtilBillListResource(BaseResource):
    def get(self):
        args = id_parser.parse_args()
        s = Session()
        # TODO: pre-join with Charge to make this faster
        utilbills = s.query(UtilBill).join(UtilityAccount).filter(
            UtilityAccount.id == args['id']).filter(
            UtilBill.discriminator == BEUtilBill.POLYMORPHIC_IDENTITY).order_by(
            desc(UtilBill.period_start), desc(UtilBill.id)).all()
        rows = [marshal(ub, self.utilbill_fields) for ub in utilbills]
        return {'rows': rows, 'results': len(rows)}


class UtilBillResource(BaseResource):
    def __init__(self):
        super(UtilBillResource, self).__init__()

    def put(self, id):
        s = Session()
        parser = id_parser.copy()
        parser.add_argument('period_start', type=parse_date)
        parser.add_argument('period_end', type=parse_date)
        parser.add_argument('target_total', type=float)
        parser.add_argument('processed', type=bool)
        parser.add_argument('rate_class_id', type=int)
        parser.add_argument('utility_id', type=int)
        parser.add_argument('supplier', type=str)
        parser.add_argument('supply_choice_id', type=str)
        parser.add_argument('supplier_id', type=int)
        parser.add_argument('supply_group', type=str)
        parser.add_argument('supply_group_id', type=int)
        parser.add_argument('total_energy', type=float)
        parser.add_argument('entered', type=bool)
        parser.add_argument('flagged', type=bool)
        parser.add_argument('next_meter_read_date', type=parse_date)
        parser.add_argument('service',
                            type=lambda v: None if v is None else v.lower())
        parser.add_argument('meter_identifier', type=str)
        parser.add_argument('tou', type=bool)
        row = parser.parse_args()

        utilbill = s.query(UtilBill).filter_by(id=id).first()

        # since 'update_utilbill_metadata' modifies the bill even when all
        # the keys are None, 'un_enter' has to come before it and 'enter' has
        #  to come after it.
        if row['entered'] is False:
            with project_mgr_permission.require():
                utilbill.un_enter()

        ub = self.utilbill_processor.update_utilbill_metadata(
            id,
            period_start=row['period_start'],
            period_end=row['period_end'],
            service=row['service'],
            target_total=row['target_total'],
            processed=row['processed'],
            rate_class=row['rate_class_id'],
            utility=row['utility_id'],
            supplier=row['supplier_id'],
            supply_choice_id=row['supply_choice_id'],
            tou=row['tou'],
            meter_identifier=row['meter_identifier'],
            supply_group_id=row['supply_group_id']
        )
        if row.get('total_energy') is not None:
            ub.set_total_energy(row['total_energy'])
        if row.get('next_meter_read_date') is not None:
            ub.set_next_meter_read_date(row['next_meter_read_date'])
        self.utilbill_processor.compute_utility_bill(id)

        if row['flagged'] is True:
            utilbill.flag()
        elif row['flagged'] is False:
            utilbill.un_flag()

        if row.get('entered') is True:
            if utilbill.discriminator == UtilBill.POLYMORPHIC_IDENTITY:
                utilbill = replace_utilbill_with_beutilbill(utilbill)
            utilbill.enter(current_user, datetime.utcnow())

        s.commit()
        return {'rows': marshal(ub, self.utilbill_fields), 'results': 1}

    def delete(self, id):
        self.utilbill_processor.delete_utility_bill_by_id(id)
        return {}


class UploadUtilityBillResource(BaseResource):

    @admin_permission.require()
    def post(self):
        s = Session()
        parser = RequestParser()
        parser.add_argument('guid', type=str, required=True)
        parser.add_argument('utility', type=int, required=True)
        parser.add_argument('utility_account_number', type=str, required=True)
        parser.add_argument('sa_addressee', type=str)
        parser.add_argument('sa_street', type=str)
        parser.add_argument('sa_city', type=str)
        parser.add_argument('sa_state', type=str)
        parser.add_argument('sa_postal_code', type=str)
        args = parser.parse_args()
        address = Address(addressee=args['sa_addressee'],
                          street=args['sa_street'], city=args['sa_city'],
                          state=args['sa_state'],
                          postal_code=args['sa_postal_code'])

        utility = s.query(Utility).filter_by(id=args['utility']).one()
        try:
            utility_account = s.query(UtilityAccount).filter_by(
                account_number=args['utility_account_number'],
                fb_utility=utility).one()
        except NoResultFound:
            last_account = s.query(
                cast(UtilityAccount.account, integer)).order_by(
                cast(UtilityAccount.account, integer).desc()).first()
            next_account = str(int(last_account[0]) + 1)
            utility_account = UtilityAccount(
                '', next_account, utility, None, None, Address(),
                address, args['utility_account_number'])
            s.add(utility_account)

        # Utility bills won't be created if there are no utility
        # bill files
        if not session.get('hash-digest'):
            raise MissingFileError()
        for hash_digest in session.get('hash-digest'):
            # skip extracting data because it's currently slow
            ub = self.utilbill_processor.create_utility_bill_with_existing_file(
                utility_account, hash_digest, service_address=address,
                skip_extraction=True)
            s.add(ub)
        # remove the consumed hash-digest from session
        session.pop('hash-digest')
        update_altitude_account_guids(utility_account, args['guid'])
        s.commit()
        # Since this is initiated by an Ajax request, we will still have to
        # send a {'success', 'true'} parameter
        return {'success': 'true'}


class ChargeListResource(BaseResource):
    def get(self):
        parser = RequestParser()
        parser.add_argument('utilbill_id', type=int, required=True)
        args = parser.parse_args()
        utilbill = Session().query(UtilBill).filter_by(
            id=args['utilbill_id']).one()
        # TODO: return only supply charges here
        rows = [marshal(c, self.charge_fields) for c in
                utilbill.get_supply_charges()]
        return {'rows': rows, 'results': len(rows)}


class UtilityBillFileResource(BaseResource):

    @admin_permission.require()
    def post(self):
        parser = RequestParser()
        parser.add_argument('file', type=werkzeug.datastructures.FileStorage, location='files', required=True)
        args = parser.parse_args()
        file = args['file']
        sha_digest = self.utilbill_processor.bill_file_handler.upload_file(file)
        if session.get('hash-digest') is None:
            session['hash-digest'] = []
        session['hash-digest'].append(sha_digest)


class ChargeResource(BaseResource):

    def put(self, id=None):
        parser = id_parser.copy()
        parser.add_argument('rsi_binding', type=str)
        parser.add_argument('target_total', type=float)
        args = parser.parse_args()

        s = Session()
        charge = s.query(Charge).filter_by(id=id).one()
        if args['rsi_binding'] is not None:
            # convert name to all caps with underscores instead of spaces
            charge.rsi_binding = args['rsi_binding'].strip().upper().replace(
                ' ', '_')
        if args['target_total'] is not None:
            charge.target_total = args['target_total']
        s.commit()
        return {'rows': marshal(charge, self.charge_fields), 'results': 1}

    def post(self, id):
        # TODO: client sends "id" even when its value is meaningless (the
        # value is always 0, for some reason)
        parser = id_parser.copy()
        parser.add_argument('utilbill_id', type=int, required=True)
        parser.add_argument('rsi_binding', type=str, required=True)
        args = parser.parse_args()
        charge = self.utilbill_processor.add_charge(
            args['utilbill_id'], rsi_binding=args['rsi_binding'],
            type=Charge.SUPPLY)
        Session().commit()
        return {'rows': marshal(charge, self.charge_fields), 'results': 1}

    def delete(self, id):
        self.utilbill_processor.delete_charge(id)
        Session().commit()
        return {}


class RSIBindingsResource(BaseResource):

    def get(self):
        rsi_bindings = Session.query(Charge.rsi_binding).distinct().all()
        rsi_bindings = [dict(name=rsi_binding[0]) for rsi_binding in rsi_bindings]
        return {'rows': rsi_bindings,
                'results': len(rsi_bindings)}



class SuppliersResource(BaseResource):
    def get(self):
        suppliers = Session().query(Supplier).all()
        rows = marshal(suppliers, {'id': Integer, 'name': String})
        return {'rows': rows, 'results': len(rows)}

    def post(self):
        parser = RequestParser()
        parser.add_argument('name', type=str, required=True)
        args = parser.parse_args()
        supplier = self.utilbill_processor.create_supplier(args['name'])
        Session().commit()
        return {'rows': marshal(supplier, {'id': Integer, 'name': String}),
                'results': 1}


class UtilitiesResource(BaseResource):
    def get(self):
        utilities = Session().query(Utility).all()
        rows = marshal(utilities, self.utility_fields)
        return {'rows': rows, 'results': len(rows)}

    def post(self):
        parser = RequestParser()
        parser.add_argument('name', type=str, required=True)
        args=parser.parse_args()
        utility = self.utilbill_processor.create_utility(args['name'])
        Session.commit()
        return {'rows': marshal(utility, self.supply_group_fields), 'results': 1 }


class RateClassesResource(BaseResource):
    def get(self):
        rate_classes = Session.query(RateClass).all()
        rows = marshal(rate_classes, {
            'id': Integer,
            'name': String,
            'utility_id': Integer,
            'service': String})
        return {'rows': rows, 'results': len(rows)}

    def post(self):
        parser = RequestParser()
        parser.add_argument('name', type=str, required=True)
        parser.add_argument('utility_id', type=int, required=True)
        parser.add_argument('service', type=str, required=True)
        args = parser.parse_args()
        rate_class = self.utilbill_processor.create_rate_class(
                            args['name'],
                            args['utility_id'],
                            args['service'].lower())
        Session().commit()
        return {'rows': marshal(rate_class,{
            'id': Integer,
            'name': String,
            'utility_id': Integer,
            'service': String
        }), 'results': 1}


class UtilBillCountForUserResource(BaseResource):

    def get(self, *args, **kwargs):
        with project_mgr_permission.require():
            parser = RequestParser()
            parser.add_argument('start', type=parse_date, required=True)
            parser.add_argument('end', type=parse_date, required=True)
            args = parser.parse_args()

            s = Session()
            count_sq = s.query(
                BEUtilBill.billentry_user_id,
                func.count(BEUtilBill.id).label('total_count'),
                func.sum(
                    case(((RateClass.service == 'electric', 1),), else_=0)
                ).label('electric_count'),
                func.sum(
                    case(((RateClass.service == 'gas', 1),), else_=0)
                ).label('gas_count')
            ).group_by(BEUtilBill.billentry_user_id).outerjoin(RateClass).filter(and_(
                BEUtilBill.billentry_date >= args['start'],
                    BEUtilBill.billentry_date < args['end'])
            ).subquery()


            q = s.query(
                BillEntryUser,
                func.max(count_sq.c.total_count),
                func.max(count_sq.c.electric_count),
                func.max(count_sq.c.gas_count),
            ).outerjoin(count_sq).group_by(
                BillEntryUser.id, BillEntryUser.email).order_by(
                BillEntryUser.id)

            rows = [{
                'id': user.id,
                'email': user.email,
                    'total_count': int(total_count or 0),
                    'gas_count': int(gas_count or 0),
                    'electric_count': int(electric_count or 0),
                    'elapsed_time': user.get_beuser_billentry_duration(args['start'], args['end'])
                } for (user, total_count, electric_count, gas_count) in q.all()]

            return {'rows': rows, 'results': len(rows)}


class UtilBillListForUserResource(BaseResource):
    """List of bills queried by id of BillEntryUser who "entered" them.
    """
    def get(self, *args):
        parser = RequestParser()
        parser.add_argument('id', type=int, required=True)
        parser.add_argument('start', type=parse_date, required=True)
        parser.add_argument('end', type=parse_date, required=True)
        args = parser.parse_args()

        s = Session()
        utilbills = s.query(BEUtilBill)\
            .join(BillEntryUser)\
            .filter(and_(
                BEUtilBill.billentry_date >= args['start'],
                BEUtilBill.billentry_date < args['end'],
                BillEntryUser.id == args['id']
            ))\
            .order_by(
                desc(UtilBill.period_start),
                desc(UtilBill.id)
            ).all()
        rows = [marshal(ub, self.utilbill_fields) for ub in utilbills]
        return {'rows': rows, 'results': len(rows)}


class FlaggedUtilBillListResource(BaseResource):
    """List of utility bills that are flagged
    """

    def get(self, *args, **kwargs):
        with project_mgr_permission.require():
            s = Session()
            utilbills = s.query(BEUtilBill)\
                .filter(BEUtilBill.flagged == True)\
                .order_by(
                    desc(UtilBill.period_start),
                    desc(UtilBill.id)
                ).all()
            rows = [marshal(ub, self.utilbill_fields) for ub in utilbills]
            return {'rows': rows, 'results': len(rows)}

