Ext.define('ReeBill.view.accounts.AccountForm', {
    extend: 'Ext.form.Panel',
    requires: [
        'ReeBill.view.accounts.AccountsCombo',
        'ReeBill.store.ServiceTypes'
    ],
    title: 'Create New Account',

    alias: 'widget.accountForm',    

    bodyPadding: 15,
    autoScroll: true,

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
        items: [{
            xtype: 'accountsCombo',
            name: 'template_account'
        },{
            xtype: 'textfield',
            fieldLabel: 'Account',
            name: 'account',
            allowBlank: false
        },{
            xtype: 'textfield',
            fieldLabel: 'Name',
            name: 'name',
            allowBlank: false
        },{
            xtype: 'textfield',
            fieldLabel: 'Discount Rate',
            name: 'discount_rate',
            allowBlank: false
        },{
            xtype: 'textfield',
            fieldLabel: 'Late Charge Rate',
            name: 'late_charge_rate',
            allowBlank: false
        },
        {
            xtype: 'textfield',
            fieldLabel: 'Utility Account Number',
            name: 'utility_account_number',
            allowBlank: false
        },
        {
            xtype: 'combobox',
            fieldLabel: 'Renewable Energy Service',
            name: 'service_type',
            allowBlank: false,
            store: 'ServiceTypes',
            queryMode: 'local',
            displayField: 'display_name',
            valueField: 'service_type',
            value: 'thermal',
            editable: false
        }]
    },{
        xtype: 'fieldset',
        title: 'Billing Address',
        defaults: {
            anchor: '100%',
            labelWidth: 150
        },
        items: [{
            xtype: 'textfield',
            fieldLabel: 'Addressee',
            name: 'ba_addressee'
        },{
            xtype: 'textfield',
            fieldLabel: 'Street',
            name: 'ba_street'
        },{
            xtype: 'textfield',
            fieldLabel: 'City',
            name: 'ba_city'
        },{
            xtype: 'textfield',
            fieldLabel: 'State',
            name: 'ba_state'
        },{
            xtype: 'textfield',
            fieldLabel: 'Postal Code',
            name: 'ba_postal_code'
        }]
    },{
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
            text: 'Save',
            iconCls: 'silk-disk',
            action: 'saveNewAccount'
        },{
            xtype: 'checkbox',
            boxLabel: 'Make Another Account',
            name: 'makeAnotherAccount'
        }]
    }]
});
