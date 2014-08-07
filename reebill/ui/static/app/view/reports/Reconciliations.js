Ext.define('ReeBill.view.Reconciliations', {
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
        width: 80
    },{
        header: 'Sequence',
        dataIndex: 'sequence',
        width: 80
    },{
        header: 'Bill Energy (therms)',
        dataIndex: 'bill_therms',
        width: 150
    },{
        header: 'OLAP Energy (therms)',
        dataIndex: 'olap_therms',
        width: 150
    },{
        header: 'OLTP Energy (therms)',
        dataIndex: 'oltp_therms',
        width: 150
    },{
        header: 'Errors (see reconcilation log for details)',
        dataIndex: 'errors'
    }],

    bbar: {
        xtype: 'pagingtoolbar',
        pageSize: 25,
        store: 'Reconciliations',
        displayInfo: true,
        displayMsg: 'Displaying {0} - {1} of {2}'
    }

});