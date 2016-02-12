Ext.define('BillEntry.view.Viewport', {
    extend: 'Ext.container.Viewport',
    layout: 'fit',
    componentCls: 'panel-noborder',

    requires: [
        'Ext.panel.PDF',
        'BillEntry.view.accounts.Accounts',
        'BillEntry.view.utilitybills.UtilityBills',
        'BillEntry.view.charges.Charges',
        'BillEntry.view.uploadbills.UploadBillsForm',
        'BillEntry.view.uploadbills.Dropzone',
        'BillEntry.view.reports.Reports'
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
                name: 'uploadBillsTab',
                title: 'Upload Utility Bills',
                layout: 'border',
                items: [{
                    xtype: 'uploadBillsForm',
                    id: 'uploadBillsForm',
                    region: 'north',
                    collapsible: false,
                    flex: 1,
                    minHeight: 200,
                    autoScroll: true
                },{
                    xtype: 'dropzone',
                    id: 'dropzone',
                    layout: 'fit',
                    region: 'center',
                    flex: 1,
                    minHeight: 200
                    }]
            },{
                xtype: 'reports'
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
