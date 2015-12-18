# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'State'
        db.create_table(u'intro_state', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('abbr', self.gf('django.db.models.fields.CharField')(max_length=40, null=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=40)),
            ('brokerage_possible', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal(u'intro', ['State'])

        # Adding model 'Address'
        db.create_table(u'intro_address', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('street1', self.gf('django.db.models.fields.CharField')(max_length=200, null=True)),
            ('street2', self.gf('django.db.models.fields.CharField')(max_length=200, null=True, blank=True)),
            ('city', self.gf('django.db.models.fields.CharField')(max_length=80, null=True)),
            ('state', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['intro.State'])),
            ('zip', self.gf('django.db.models.fields.CharField')(max_length=10, null=True)),
        ))
        db.send_create_signal(u'intro', ['Address'])

        # Adding model 'Account'
        db.create_table(u'intro_account', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('address', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['intro.Address'], null=True)),
            ('first_name', self.gf('django.db.models.fields.CharField')(max_length=40, null=True, blank=True)),
            ('last_name', self.gf('django.db.models.fields.CharField')(max_length=40, null=True, blank=True)),
            ('guid', self.gf('django.db.models.fields.CharField')(max_length=36, unique=True, null=True)),
            ('token', self.gf('django.db.models.fields.CharField')(max_length=60, unique=True, null=True)),
            ('tandc1_signed', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, null=True, blank=True)),
        ))
        db.send_create_signal(u'intro', ['Account'])

        # Adding model 'User'
        db.create_table(u'intro_user', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('password', self.gf('django.db.models.fields.CharField')(max_length=128)),
            ('last_login', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.now)),
            ('is_superuser', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('email_address', self.gf('django.db.models.fields.CharField')(unique=True, max_length=80, db_index=True)),
            ('email_address_verified', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('identifier', self.gf('django.db.models.fields.CharField')(max_length=40, null=True, blank=True)),
            ('account_status', self.gf('django.db.models.fields.PositiveSmallIntegerField')(default=50)),
            ('account', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['intro.Account'], null=True, blank=True)),
            ('first_name', self.gf('django.db.models.fields.CharField')(max_length=40, null=True, blank=True)),
            ('last_name', self.gf('django.db.models.fields.CharField')(max_length=40, null=True, blank=True)),
            ('is_admin', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal(u'intro', ['User'])

        # Adding M2M table for field groups on 'User'
        m2m_table_name = db.shorten_name(u'intro_user_groups')
        db.create_table(m2m_table_name, (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('user', models.ForeignKey(orm[u'intro.user'], null=False)),
            ('group', models.ForeignKey(orm[u'auth.group'], null=False))
        ))
        db.create_unique(m2m_table_name, ['user_id', 'group_id'])

        # Adding M2M table for field user_permissions on 'User'
        m2m_table_name = db.shorten_name(u'intro_user_user_permissions')
        db.create_table(m2m_table_name, (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('user', models.ForeignKey(orm[u'intro.user'], null=False)),
            ('permission', models.ForeignKey(orm[u'auth.permission'], null=False))
        ))
        db.create_unique(m2m_table_name, ['user_id', 'permission_id'])

        # Adding model 'Token'
        db.create_table(u'intro_token', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['intro.User'])),
            ('token', self.gf('django.db.models.fields.CharField')(unique=True, max_length=60)),
            ('purpose', self.gf('django.db.models.fields.CharField')(max_length=20)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('expires', self.gf('django.db.models.fields.DateTimeField')()),
        ))
        db.send_create_signal(u'intro', ['Token'])

        # Adding model 'UtilityProvider'
        db.create_table(u'intro_utilityprovider', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=50)),
            ('short_name', self.gf('django.db.models.fields.CharField')(max_length=10, null=True, blank=True)),
            ('registrationrule', self.gf('django.db.models.fields.PositiveSmallIntegerField')()),
        ))
        db.send_create_signal(u'intro', ['UtilityProvider'])

        # Adding model 'UtilityWebsiteInformation'
        db.create_table(u'intro_utilitywebsiteinformation', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('utility_username', self.gf('django.db.models.fields.CharField')(max_length=64)),
            ('utility_password', self.gf('django.db.models.fields.CharField')(max_length=64)),
            ('utility_provider', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['intro.UtilityProvider'])),
            ('account', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['intro.Account'])),
        ))
        db.send_create_signal(u'intro', ['UtilityWebsiteInformation'])

        # Adding model 'UtilityAccountInformation'
        db.create_table(u'intro_utilityaccountinformation', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('utility_account_number', self.gf('django.db.models.fields.CharField')(max_length=40, null=True, blank=True)),
            ('address', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['intro.Address'], null=True, blank=True)),
            ('utility_provider', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['intro.UtilityProvider'], null=True)),
            ('account', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['intro.Account'])),
            ('verified', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal(u'intro', ['UtilityAccountInformation'])


    def backwards(self, orm):
        # Deleting model 'State'
        db.delete_table(u'intro_state')

        # Deleting model 'Address'
        db.delete_table(u'intro_address')

        # Deleting model 'Account'
        db.delete_table(u'intro_account')

        # Deleting model 'User'
        db.delete_table(u'intro_user')

        # Removing M2M table for field groups on 'User'
        db.delete_table(db.shorten_name(u'intro_user_groups'))

        # Removing M2M table for field user_permissions on 'User'
        db.delete_table(db.shorten_name(u'intro_user_user_permissions'))

        # Deleting model 'Token'
        db.delete_table(u'intro_token')

        # Deleting model 'UtilityProvider'
        db.delete_table(u'intro_utilityprovider')

        # Deleting model 'UtilityWebsiteInformation'
        db.delete_table(u'intro_utilitywebsiteinformation')

        # Deleting model 'UtilityAccountInformation'
        db.delete_table(u'intro_utilityaccountinformation')


    models = {
        u'auth.group': {
            'Meta': {'object_name': 'Group'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        u'auth.permission': {
            'Meta': {'ordering': "(u'content_type__app_label', u'content_type__model', u'codename')", 'unique_together': "((u'content_type', u'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['contenttypes.ContentType']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        u'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        u'intro.account': {
            'Meta': {'object_name': 'Account'},
            'address': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['intro.Address']", 'null': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '40', 'null': 'True', 'blank': 'True'}),
            'guid': ('django.db.models.fields.CharField', [], {'max_length': '36', 'unique': 'True', 'null': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '40', 'null': 'True', 'blank': 'True'}),
            'tandc1_signed': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'null': 'True', 'blank': 'True'}),
            'token': ('django.db.models.fields.CharField', [], {'max_length': '60', 'unique': 'True', 'null': 'True'})
        },
        u'intro.address': {
            'Meta': {'object_name': 'Address'},
            'city': ('django.db.models.fields.CharField', [], {'max_length': '80', 'null': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'state': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['intro.State']"}),
            'street1': ('django.db.models.fields.CharField', [], {'max_length': '200', 'null': 'True'}),
            'street2': ('django.db.models.fields.CharField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'zip': ('django.db.models.fields.CharField', [], {'max_length': '10', 'null': 'True'})
        },
        u'intro.state': {
            'Meta': {'object_name': 'State'},
            'abbr': ('django.db.models.fields.CharField', [], {'max_length': '40', 'null': 'True'}),
            'brokerage_possible': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '40'})
        },
        u'intro.token': {
            'Meta': {'object_name': 'Token'},
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'expires': ('django.db.models.fields.DateTimeField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'purpose': ('django.db.models.fields.CharField', [], {'max_length': '20'}),
            'token': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '60'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['intro.User']"})
        },
        u'intro.user': {
            'Meta': {'object_name': 'User'},
            'account': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['intro.Account']", 'null': 'True', 'blank': 'True'}),
            'account_status': ('django.db.models.fields.PositiveSmallIntegerField', [], {'default': '50'}),
            'email_address': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80', 'db_index': 'True'}),
            'email_address_verified': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '40', 'null': 'True', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['auth.Group']", 'symmetrical': 'False', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'identifier': ('django.db.models.fields.CharField', [], {'max_length': '40', 'null': 'True', 'blank': 'True'}),
            'is_admin': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '40', 'null': 'True', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        u'intro.utilityaccountinformation': {
            'Meta': {'object_name': 'UtilityAccountInformation'},
            'account': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['intro.Account']"}),
            'address': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['intro.Address']", 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'utility_account_number': ('django.db.models.fields.CharField', [], {'max_length': '40', 'null': 'True', 'blank': 'True'}),
            'utility_provider': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['intro.UtilityProvider']", 'null': 'True'}),
            'verified': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        u'intro.utilityprovider': {
            'Meta': {'object_name': 'UtilityProvider'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'registrationrule': ('django.db.models.fields.PositiveSmallIntegerField', [], {}),
            'short_name': ('django.db.models.fields.CharField', [], {'max_length': '10', 'null': 'True', 'blank': 'True'})
        },
        u'intro.utilitywebsiteinformation': {
            'Meta': {'object_name': 'UtilityWebsiteInformation'},
            'account': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['intro.Account']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'utility_password': ('django.db.models.fields.CharField', [], {'max_length': '64'}),
            'utility_provider': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['intro.UtilityProvider']"}),
            'utility_username': ('django.db.models.fields.CharField', [], {'max_length': '64'})
        }
    }

    complete_apps = ['intro']