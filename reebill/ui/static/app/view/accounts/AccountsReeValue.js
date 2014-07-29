Ext.define('ReeBill.view.AccountsReeValue', {
    extend: 'Ext.grid.Panel',

    title: 'Summary and Export',
    alias: 'widget.accountsReeValue',    
    store: 'AccountsReeValue',
    
    viewConfig: {
        trackOver: false,
        stripeRows: true
    },
    
    columns: [
        {header: 'Account', dataIndex: 'account'},
        {header: 'OLAP ID', dataIndex: 'olap_id'},        
        {header: 'Casual Name', dataIndex: 'casualname'},
        {header: 'Primus Name', dataIndex: 'primusname'},
        {header: 'REE Charges', dataIndex: 'ree_charges'},        
        {header: 'Total Utility Charges', dataIndex: 'actual_charges'},
        {header: 'Hypothesized Utility Charges', dataIndex: 'hypothetical_charges'},
        {header: 'Total Energy', dataIndex: 'total_energy'},
        {header: 'Average Value per Therm of RE', dataIndex: 'average_ree_rate'},
        {header: 'Outstanding Balance', dataIndex: 'outstandingbalance'},
        {header: 'Days Overdue', dataIndex: 'days_late'}
    ],

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

    bbar: {
        xtype: 'pagingtoolbar',
        pageSize: 25,
        store: 'AccountsReeValue',
        displayInfo: true,
        displayMsg: 'Displaying {0} - {1} of {2}'
    }
});