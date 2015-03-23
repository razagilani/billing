Ext.define('BillEntry.view.Viewport', {
    extend: 'Ext.container.Viewport',
    layout: 'fit',
    componentCls: 'panel-noborder',

    requires: [
        'Ext.panel.PDF',
        'BillEntry.view.accounts.Accounts',
        'BillEntry.view.utilitybills.UtilityBills',
        'BillEntry.view.charges.Charges',
        'BillEntry.view.reports.UserStatistics',
        'BillEntry.view.reports.BillDetails'
    ],

    items: {
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
            html: '<div id="header" style="background:#00a4e4; height:inherit;"><img src="images/nextility_blue.png" style="height:inherit; padding:3px"></div>'
        },{
            region: 'west',
            xtype: 'pdfpanel',
            name: 'utilityBillViewer',
            collapsible: true,
            collapsed: false,
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
                defaults: {
                    collapsible: true,
                    split: true
                },
                items: [{
                    xtype: 'utilityBills',
                    id: 'utilityBillsGrid',
                    region: 'center',
                    collapsible: false
                },{
                    xtype: 'charges',
                    id: 'chargesGrid',
                    region: 'south',
                    height: 150
                }]
            },{
                xtype: 'panel',
                name: 'reportsTab',
                title: 'Reports',
                layout: {
                    type: 'vbox',
                    align : 'stretch',
                    pack  : 'start'
                },
                items: [{
                    xtype: 'form',
                    height: 60,
                    title: 'Select a Date/Time Range',
                    items: {
                        xtype: 'fieldcontainer',
                        layout: 'hbox',
                        fieldDefaults: {
                            labelWidth: 75,
                            allowBlank: false,
                            flex: 1,
                            margin: '2 5 5 5'
                        },
                        items: [{
                            xtype: 'datefield',
                            fieldLabel: 'From:',
                            name: 'start'
                        }, {
                            xtype: 'datefield',
                            fieldLabel: 'To:',
                            name: 'end'
                            //},{
                            //    xtype: 'button',
                            //    formBind: true,
                            //    disabled: true
                        }]
                    }
                },{
                    xtype: 'userStatistic',
                    flex: 1
                },{
                    xtype: 'billDetails',
                    id: 'reportUtilityBillsGrid',
                    flex: 1
                }]
            }],

            dockedItems: [{
                xtype: 'toolbar',
                dock: 'bottom',

                items:[{
                    text: 'Log Out',
                    handler: function(){
                        window.location.pathname = '/logout';
                    }
                },'->',{
                    xtype: 'tbtext',
                    name: 'revisionTBLabel',
                    text: VERSION.date + ' ' + VERSION.user + ' ' + VERSION.version + ' ' + VERSION.deploy_env
                },'->']
            }]
        }]
    }
});
