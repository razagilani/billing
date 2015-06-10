Ext.define('BillEntry.view.uploadbills.UploadBillsForm', {
    extend: 'Ext.form.Panel',

    title: 'Bills Metadata',

    alias: 'widget.uploadBillsForm',

    requires: ['BillEntry.store.AltitudeAccounts'],

    bodyPadding: 15,
    titleCollapse: true,
    floatable: false,

    defaults: {
        anchor: '100%'
    },

    items: [{
        xtype: 'fieldset',
        title: 'Account Information',
        defaults: {
            anchor: '100%',
            labelWidth: 150
        },
        collapsible: false,
        items:[{
            xtype: 'combo',
            fieldLabel: 'Account GUID',
            store: 'AltitudeAccounts',
            itemId: 'altitude_account_combo',
            displayField: 'guid',
            valueField: 'guid',
            triggerAction: 'all',
            forceSelection: false,
            typeAhead: true,
            typeAheadDelay : 1,
            autoSelect: false,
            regex: /[a-zA-Z0-9]+/,
            minChars: 1
        },{
            xtype: 'combo',
            fieldLabel: 'Utility',
            name: 'utility',
            store: 'Utilities',
            triggerAction: 'all',
            valueField: 'id',
            displayField: 'name',
            forceSelection: false,
            typeAhead: true,
            typeAheadDelay : 1,
            autoSelect: false,
            regex: /[a-zA-Z0-9]+/,
            minChars: 1
        },{
            xtype: 'textfield',
            fieldLabel: 'Utility Account Number',
            name: 'utility_account_number',
            allowBlank: false
        }]
    }, {
        xtype: 'fieldset',
        title: 'Service Address',
        defaults: {
            anchor: '100%',
            labelWidth: 150
        },
        items: [{
            xtype: 'textfield',
            fieldLabel: 'Addressee',
            name: 'sa_addressee'
        },{
            xtype: 'textfield',
            fieldLabel: 'Street',
            name: 'sa_street'
        },{
            xtype: 'textfield',
            fieldLabel: 'City',
            name: 'sa_city'
        },{
            xtype: 'textfield',
            fieldLabel: 'State',
            name: 'sa_state'
        },{
            xtype: 'textfield',
            fieldLabel: 'Postal Code',
            name: 'sa_postal_code'
        }]
    }],

    dockedItems: [{
        dock: 'bottom',
        xtype: 'toolbar',
        items: ['->',{
            xtype: 'button',
            action: 'resetUploadBillsForm',
            text: 'Reset'
        },{
            xtype: 'button',
            action: 'submitUploadBillsForm',
            text: 'Submit'
        }]
    }]

});

