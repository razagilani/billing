Ext.define('ReeBill.view.reebills.SequentialAccountInformation', {
    extend: 'Ext.form.Panel',

    title: 'Sequential Account Information',

    alias: 'widget.sequentialAccountInformation',    

    bodyPadding: 15,
    autoScroll: true,

    defaults: {
        anchor: '100%'
    },

    items: [{
        xtype: 'reeBillVersions',
        name: 'reeBillVersions',
        region: 'north'
    },{
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
            name: 'late_charge_rate',
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
            action: 'saveAccountInformation'
        },{
            xtype: 'button',
            text: 'Reset',
            action: 'resetAccountInformation'
        }]
    }]
});
