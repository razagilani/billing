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
            //},{
            //    region: 'east',
            //    xtype: 'pdfpanel',
            //    name: 'reebillViewer',
            //    collapsible: true,
            //    collapsed: true,
            //    cache: false,
            //    src: '',
            //    width: Ext.getBody().getWidth() * 0.3
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
                    name: 'utilityBillsTab',
                    title: 'Utility Bills',
                    layout: 'border',
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
                        floatable: false,
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
                        region: 'center'
                    }]
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
                            window.location.pathname = 'utilitybills/logout';
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
