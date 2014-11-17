Ext.define('ReeBill.view.reports.Exports', {
    extend: 'Ext.panel.Panel',

    title:'Exports',
    header: false,
    alias: 'widget.exports',

    
    dockedItems: [{
        dock: 'top',
        xtype: 'toolbar',
        layout: {
            overflowHandler: 'Menu'
        },
        items: [{
            xtype: 'button',
            text: 'Export ReeBill XLS',
            iconCls: 'silk-application-go',
            action: 'exportRebill'
        },{
            xtype: 'button',
            text: 'Export Utility Bills to XLS',
            iconCls: 'silk-application-go',
            action: 'exportUtilityBills'
        },{
            xtype: 'button',
            text: '12 Month Estimated Revenue',
            iconCls: 'silk-application-go',
            action: 'export12MonthRevenue'
        }]
    }],

});
