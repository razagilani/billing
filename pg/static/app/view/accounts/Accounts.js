Ext.define('ReeBill.view.accounts.Accounts', {
    extend: 'Ext.grid.Panel',
    requires: [],
    title: 'Accounts',
    alias: 'widget.accounts',   
    store: 'Accounts',

    plugins: [
        Ext.create('Ext.grid.plugin.CellEditing', {
            clicksToEdit: 2
        })
    ],
    
    viewConfig: {
        trackOver: false,
        stripeRows: true,
        getRowClass: function(record) {
            if (record.get('provisionable'))
                return 'account-grid-gray';
        }
    },
    
    columns: [{
        header: 'Nextily Account Number',
        dataIndex: 'account',
        width: 100
    }, {
        header: 'Utility Account Number',
        dataIndex: 'utility_account_number',
        editor: {
            xtype: 'textfield'
        },
        width: 100
    }]

});
