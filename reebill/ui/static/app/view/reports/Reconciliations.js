Ext.define('ReeBill.view.reports.Reconciliations', {
    extend: 'Ext.grid.Panel',

    title:'Reconcilation Report',
    alias: 'widget.reconciliations',    
    store: 'Reconciliations',
    
    viewConfig: {
        trackOver: false,
        stripeRows: true,
        getRowClass: function(record) {

        }
    },
    
    columns: [{
        header: 'Customer ID',
        dataIndex: 'customer_id',
        width: 120
    },{
        header: 'Sequence',
        dataIndex: 'sequence',
        width: 120
    },{
        header: 'Bill Energy',
        dataIndex: 'energy',
        width: 200
    },{
        header: 'Current Energy',
        dataIndex: 'current_energy',
        width: 200,
        flex: 1
    }],

    bbar: {
        xtype: 'pagingtoolbar',
        pageSize: 25,
        store: 'Reconciliations',
        displayInfo: true,
        displayMsg: 'Displaying {0} - {1} of {2}'
    }

});
