Ext.define('ReeBill.view.Viewport', {
    extend: 'Ext.container.Viewport',
    layout: 'fit',
    componentCls: 'panel-noborder',

    requires: ['Ext.panel.PDF'],

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
                height: 30,
                split: false,
                border: false,
                html: '<div id="header" style="background:#00a4e4; height:inherit;"><img src="static/images/nextility_blue.png" style="height:inherit; padding:3px"></div>'
            },{
                region: 'west',
                xtype: 'pdfpanel',
                name: 'utilityBillViewer',
                collapsible: true,
                collapsed: false,
                src: '',
                width: Ext.getBody().getWidth() * 0.3
            },{
                region: 'east',
                xtype: 'pdfpanel',
                name: 'reebillViewer',
                collapsible: true,
                collapsed: true,
                cache: false,
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
                    xtype: 'accounts',
                    id: 'accountsGrid'
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
                        xtype: 'utilityBillRegisters',
                        id: 'utilityBillRegistersGrid',
                        region: 'center',
                        collapsible: false
                    },{
                        xtype: 'TOUMetering',
                        id: 'TOUMeteringForm',
                        region: 'south',
                        collapsible:false,
                        floatable: false
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
                        xtype: 'charges',
                        id: 'chargesGrid',
                        region: 'center',
                        store: 'Charges'
                    },{
                        xtype: 'previouscharges',
                        id: 'previousChargesGrid',
                        region: 'south',
                        store: 'PreviousCharges'
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
                    defaults: {
                            collapsible: true
                    },
                    disabled: true,
                    items: [{
                        xtype: 'reebills',
                        id: 'reebillsGrid'
                    },{
                        xtype: 'sequentialAccountInformation',
                        id: 'sequentialAccountInformationForm',
                        disabled: true
                    },{
                        xtype: 'uploadIntervalMeter',
                        id: 'uploadIntervalMeterForm',
                        disabled: true
                    }]
                },{
                    xtype: 'panel',
                    name: 'reebillChargesTab',
                    title: 'Reebill Charges',
                    layout: 'border',
                    disabled: true,
                    items: [{
                        xtype: 'panel',
                        title: 'Reebill Charges',
                        region: 'north'
                    },{
                        xtype: 'reeBillVersions',
                        name: 'reeBillChargesVersions',
                        region: 'north'
                    },{
                        xtype: 'reebillCharges',
                        id: 'reebillChargesGrid',
                        region: 'center'
                    }]
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
                    layout: 'border',
                    items: [{
                        xtype: 'accountDatePicker',
                        id: 'accountDatePicker'
                    },{
                        xtype: 'exports',
                        id: 'exportsGrid',
                        region: 'north'
                    },{
                        xtype: 'panel',
                        header: false,
                        layout: 'accordion',
                        region: 'center',
                        items: [{
                            xtype: 'reconciliations',
                            id: 'reconciliationsGrid'
                        },{
                            xtype: 'estimatedRevenue',
                            id: 'estimatedRevenueGrid'
                        },]
                    }]
                },{
                    xtype: 'preferencesPanel',
                    name: 'preferencesPanel'
                }],

                dockedItems: [{
                    xtype: 'toolbar',
                    dock: 'bottom',

                    items:["Logged in as :",
                    {
                        xtype: 'tbtext',
                        name: 'userTBLabel',
                        text: 'Username'
                    },{
                        text: 'Logout',
                        handler: function(){
                            window.location.pathname = '/reebill/logout';
                        }
                    },'->',{
                        xtype: 'tbtext',
                        name: 'revisionTBLabel',
                        text: VERSION.date + ' ' + VERSION.user + ' ' + VERSION.version + ' ' + VERSION.deploy_env
                    },'->',{
                        xtype: 'tbtext',
                        name: 'accountTBLabel',
                        text: 'No Account Selected'
                    },{
                        xtype: 'tbtext',
                        name: 'ubSequenceTBLabel',
                        text: ''
                    },{
                        xtype: 'tbtext',
                        name: 'rbSequenceVersionTBLabel',
                        text: ''
                    }]
                  }]
            }]
        };
        
        this.callParent();
    }
});
