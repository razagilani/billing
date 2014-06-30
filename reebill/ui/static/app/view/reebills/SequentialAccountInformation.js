Ext.define('ReeBill.view.SequentialAccountInformation', {
    extend: 'Ext.form.Panel',

    title: 'Sequential Account Information',

    alias: 'widget.sequentialAccountInformation',    

    bodyPadding: 15,
    autoScroll: true,

    defaults: {
        anchor: '100%'
    },

    items: [{
        xtype: 'fieldset',
        title: 'Rates',
        defaults: {
            anchor: '100%',
            labelWidth: 150
        },
        collapsible: false,
        items: [{
            xtype: 'textfield',
            name: 'discount_rate',
            fieldLabel: 'Discount Rate'
        },{
            xtype: 'textfield',
            fieldLabel: 'Late Charge Rate',
            msgTarget: 'under'
        }]
    },{
        xtype: 'fieldset',
        title: 'Skyline Billing Address',
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
        title: 'Skyline Service Address',
        defaults: {
            anchor: '100%',
            labelWidth: 150
        },
        items: [{
            xtype: 'textfield',
            fieldLabel: 'Addressee',
            name: 'new_sa_addressee'
        },{
            xtype: 'textfield',
            fieldLabel: 'Street',
            name: 'new_sa_street'
        },{
            xtype: 'textfield',
            fieldLabel: 'City',
            name: 'new_sa_city'
        },{
            xtype: 'textfield',
            fieldLabel: 'State',
            name: 'new_sa_state'
        },{
            xtype: 'textfield',
            fieldLabel: 'Postal Code',
            name: 'new_sa_postal_code'
        }]
    }],

    dockedItems: [{
        dock: 'bottom',
        xtype: 'toolbar',
        items: ['->',{
            xtype: 'button',
            text: 'Save',
            action: 'saveNewAccount'
        },{
            xtype: 'button',
            text: 'Reset',
            action: 'reset'
        }]
    }]
});