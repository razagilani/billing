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
        header: 'ID',
        dataIndex: 'id',
        width: 50,
        items: utils.makeGridFilterTextField('id')
    }, {
        header: 'Billing Account Number',
        dataIndex: 'account',
        width: 150,
        items: utils.makeGridFilterTextField('account')
    }, {
        header: 'Utility',
        dataIndex: 'utility',
        width: 120,
        items: utils.makeGridFilterTextField('utility')
    }, {
        header: 'Utility Account Number',
        dataIndex: 'utility_account_number',
        width: 150,
        items: utils.makeGridFilterTextField('utility_account_number')
    }, {
        header: 'Service Address',
        dataIndex: 'service_address',
        minWidth: 150,
        flex:1,
        items: utils.makeGridFilterTextField('service_address')
    }]

});
