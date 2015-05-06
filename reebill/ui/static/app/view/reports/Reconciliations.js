Ext.define('ReeBill.view.reports.Reconciliations', {
    extend: 'Ext.grid.Panel',

    title:'Reconcilation Report: reebills with >0.1% difference from OLTP or errors',
    alias: 'widget.reconciliations',    
    store: 'Reconciliations',
    
    viewConfig: {
        trackOver: false,
        stripeRows: true,
        getRowClass: function(record) {

        }
    },
    
    columns: [{
        header: 'Account',
        dataIndex: 'account',
        width: 120
    },{
        header: 'Sequence',
        dataIndex: 'sequence',
        width: 120
    },{
        header: 'Bill Energy (therms)',
        dataIndex: 'bill_therms',
        width: 200
    },{
        header: 'OLAP Energy (therms)',
        dataIndex: 'olap_therms',
        width: 200
    },{
        header: 'OLTP Energy (therms)',
        dataIndex: 'oltp_therms',
        width: 200
    },{
        header: 'Errors (see reconcilation log for details)',
        dataIndex: 'errors',
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
