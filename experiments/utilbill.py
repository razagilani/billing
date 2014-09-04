import mongoengine
from mongoengine.base import ValidationError
from mongoengine import Document, EmbeddedDocument
from mongoengine import StringField, IntField, FloatField, BooleanField
from mongoengine import DateTimeField, ListField, DictField
from mongoengine import EmbeddedDocumentField
from mongoengine import ObjectIdField
'''MongoEngine schema definition for utility bill documents. Move this into
mongo.py when it's done.'''

class Register(EmbeddedDocument):
    quantity_units = StringField(required=True)
    quantity = FloatField(required=True)
    register_binding = StringField(required=True)
    identifier = StringField(required=True)
    type = StringField(required=True)
    description = StringField(required=True)

class Meter(EmbeddedDocument):
    registers = ListField(field=EmbeddedDocumentField(Register))
    identifier = StringField(required=True)
    prior_read_date = DateTimeField(required=True)
    present_read_date = DateTimeField(required=True)
    estimated = BooleanField(required=True)

class Charge(EmbeddedDocument):
    rsi_binding = StringField(required=True)
    description = StringField(required=True)
    uuid = StringField(required=True)
    quantity_units = StringField(required=True)
    quantity = FloatField(required=True)
    rate = FloatField(required=True)
    total = FloatField(required=True)

class UtilBill(Document):
    meta = {
        # "db_alias" tells MongoEngine which database this goes with, while
        # still allowing it to be configurable.
        'db_alias': 'utilbills',
        'collection': 'utilbills',
        'allow_inheritance': False
    }

    _id = ObjectIdField(required=True)

    # unofficially unique identifying fields
    account = StringField(required=True)
    utility = StringField(required=True)
    service = StringField(required=True)
    start = DateTimeField(required=True) # Mongo does not have plain dates
    end = DateTimeField(required=True)

    # other fields
    chargegroups = DictField(required=True,
            field=ListField(field=EmbeddedDocumentField(Charge)))
    total = FloatField(required=True)
    rate_class = StringField(required=True)
    service_address = DictField(required=True, field=StringField())
    billing_address = DictField(required=True, field=StringField())
    meters = ListField(field=EmbeddedDocumentField(Meter), required=True)

if __name__ == '__main__':
    mongoengine.connect('skyline-dev', host='localhost', port=27017, alias='utilbills')
    try:
        for u in UtilBill.objects():
            print u.account, u.start
            #for gp, charges in u.chargegroups.iteritems():
                #print '%s:\n%s' % (
                    #gp,
                    #'\n'.join('\t%s' % c.total for c in charges)
                #)
                #print group, charges
    except ValidationError as ve:
        import ipdb; ipdb.set_trace()
        
