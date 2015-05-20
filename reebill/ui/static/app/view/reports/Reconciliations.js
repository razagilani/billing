var the_renderer = function(value, metaData, record){
    console.log(value, metaData, record);
    if (record.raw.energy == null)
        return 'not included';
    return value;
};

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
        header: 'Nextility Account Number',
        dataIndex: 'nextility_account_number',
        width: 120
    },{
        header: 'Sequence',
        dataIndex: 'sequence',
        width: 120
    },{
        header: 'Bill Energy',
        dataIndex: 'energy',
        renderer: the_renderer,
        width: 200
    },{
        header: 'Current Energy',
        dataIndex: 'current_energy',
        renderer: the_renderer,
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
