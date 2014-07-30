Ext.define('ReeBill.view.Viewport', {

    extend: 'Ext.container.Viewport',
    layout: 'fit',

    initComponent: function() {
        this.items = {
            layout: 'border',
            defaults: {
                collapsible: false,
                split: true
            },
            items: [{
                region: 'north',
                xtype: 'panel',
                layout: 'fit',
                height: 80,
                split: false,
                border: false,
                html: '<div id="header" style="background-image:url(\'static/images/green_stripe.jpg\');"><table style="border-collapse: collapse;"><tr><td><img src="static/images/skyline_logo.png"/></td><td><img src="static/images/reebill_logo.png"/></td><td style="width: 85%; text-align: right;"><img src="static/images/money_chaser.png"/></td></tr></table></div>'
            },{
                region: 'west',
                xtype: 'pdfpanel',
                name: 'utilityBillViewer',
                pageScale: 0.5,
                collapsible: true,
                collapsed: true,
                src: '',
                width: Ext.getBody().getWidth() * 0.3
            },{
                region: 'east',
                xtype: 'pdfpanel',
                name: 'reebillViewer',
                collapsible: true,
                collapsed: true,
                pageScale: 0.5,
                src: '',
                width: Ext.getBody().getWidth() * 0.3
            },{
                xtype: 'tabpanel',
                region: 'center',
                name: 'applicationTab',

                defaults: {
                    collapsible: true,
                    split: true
                },

                layout: {
                    type: 'vbox',
                    align: 'stretch'
                },
                
                items: [{
                    xtype: 'panel',
                    name: 'accountsTab',
                    title: 'Accounts',
                    layout: 'accordion',
                    defaults: {
                        collapsible: true
                    },
                    items: [{
                        xtype: 'accounts',
                        id: 'accountsGrid'
                    },{
                        xtype: 'accountsReeValue',
                        id: 'accountsReeValueGrid'
                    },{
                        xtype: 'accountForm',
                        id: 'newAccountForm'
                    }]
                },{
                    xtype: 'panel',
                    name: 'utilityBillsTab',
                    title: 'Utility Bills',
                    layout: 'border',
                    disabled: true,
                    defaults: {
                        collapsible: true,
                        split: true
                    },
                    items: [{
                        xtype: 'uploadUtilityBill',
                        id: 'uploadUtilityBill',
                        region: 'north'
                    },{
                        xtype: 'utilityBills',
                        id: 'utilityBillsGrid',
                        region: 'center',
                        collapsible: false
                    }]
                },{
                    xtype: 'panel',
                    name: 'metersTab',
                    title: 'Meters and Registers',
                    layout: 'border',
                    disabled: true,
                    defaults: {
                        collapsible: true,
                        split: true
                    },
                    items: [{
                        xtype: 'reeBillVersions',
                        region: 'north'
                    },{
                        xtype: 'utilityBillRegisters',
                        id: 'utilityBillRegistersGrid',
                        region: 'center',
                        collapsible: false
                    },{
                        xtype: 'uploadIntervalMeter',
                        id: 'uploadIntervalMeterForm',
                        region: 'south',
                        collapsible: false,
                        disabled: true
                    }]
                },{
                    xtype: 'panel',
                    name: 'rateStructuresTab',
                    title: 'Rate Structure',
                    layout: 'border',
                    disabled: true,
                    defaults: {
                        collapsible: true,
                        split: true
                    },
                    items: [{
                        xtype: 'reeBillVersions',
                        region: 'north'
                    },{
                        xtype: 'rateStructures',
                        id: 'rateStructuresGrid',
                        region: 'center'                        
                    }]
                },{
                    xtype: 'panel',
                    name: 'chargesTab',
                    title: 'Charges',
                    layout: 'border',
                    disabled: true,
                    defaults: {
                        collapsible: true,
                        split: true
                    },
                    items: [{
                        xtype: 'reeBillVersions',
                        region: 'north'
                    },{
                        xtype: 'charges',
                        id: 'chargesGrid',
                        region: 'center'
                    }]
                },{
                    xtype: 'payments',
                    id: 'paymentsGrid',
                    disabled: true
                },{
                    xtype: 'panel',
                    name: 'reebillsTab',
                    title: 'Reebills',
                    layout: 'accordion',
                    disabled: true,
                    defaults: {
                        collapsible: true
                    },
                    items: [{
                        xtype: 'reebills',
                        id: 'reebillsGrid'
                    },{
                        xtype: 'sequentialAccountInformation',
                        id: 'sequentialAccountInformationForm'
                    }]
                },{
                    xtype: 'reebillCharges',
                    id: 'reebillChargesGrid',
                    disabled: true
                },{
                    xtype: 'issuableReebills',
                    id: 'issuableReebillsGrid'
                },{
                    xtype: 'panel',
                    name: 'journalTab',
                    title: 'Journal',
                    layout: 'border',
                    items: [{
                        xtype: 'noteForm',
                        region: 'north',
                        id: 'noteForm'
                    },{
                        xtype: 'journalEntries',
                        region: 'center',
                        id: 'journalEntriesGrid'
                    }]
                },{
                    xtype: 'panel',
                    name: 'reportsTab',
                    title: 'Reports',
                    layout: 'accordion',
                    defaults: {
                        collapsible: true
                    },
                    items: [{
                        xtype: 'reconciliations',
                        id: 'reconciliationsGrid'
                    }]
                }]
            }]
        };
        
        this.callParent();
    }
});