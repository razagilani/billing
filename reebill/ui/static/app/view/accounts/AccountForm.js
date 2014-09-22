// The data store containing the list of states
var service_types = Ext.create('Ext.data.Store', {
    fields: ['display_name', 'service_type'],
    data : [
        {display_name: 'Thermal', service_type: 'thermal'},
        {display_name: 'PV', service_type: 'pv'},
        {display_name: 'None', service_type: null},
    ]
});

Ext.define('ReeBill.view.AccountForm', {
    extend: 'Ext.form.Panel',

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
            name: 'template_account',
        },{
            xtype: 'textfield',
            fieldLabel: 'Account',
            name: 'account',
            allowBlank: false,
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
            allowBlank: false,
        },{
            xtype: 'combobox',
            fieldLabel: 'Renewable Energy Service',
            name: 'service_type',
            width: 100,
            maxWidth: 100, // TODO: how do i make this work?
            allowBlank: false,
            allowBlank: false,
            store: service_types,
            queryMode: 'local',
            displayField: 'display_name',
            valueField: 'service_type',
            value: 'thermal',
            editable: false,
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
