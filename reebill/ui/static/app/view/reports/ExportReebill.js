Ext.define('ReeBill.view.Exports', {
    extend: 'Ext.panel.Panel',

    title:'Exports',
    header: false,
    alias: 'widget.exports',

    
    dockedItems: [{
        dock: 'top',
        xtype: 'toolbar',
        items: [{
            xtype: 'button',
            text: 'Export ReeBill XLS',
            iconCls: 'silk-application-go',
            action: 'exportRebill'
        },{
            xtype: 'button',
            text: 'Export All Utility Bills to XLS',
            iconCls: 'silk-application-go',
            action: 'exportAll'
        },{
            xtype: 'button',
            text: 'Export Selected Account\'s Utility Bills to XLS',
            iconCls: 'silk-application-go',
            action: 'exportSelected'
        }]
    }],

});