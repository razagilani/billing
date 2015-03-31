Ext.define('BillEntry.view.accounts.Accounts', {
    extend: 'Ext.grid.Panel',
    requires: ['BillEntry.store.AccountsFilter'],
    title: 'Accounts',
    id: 'AccountsGrid',
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
            else if (record.get('bills_to_be_entered'))
                return 'account-grid-blue';
        }
    },
    
    columns: [{
        header: 'ID',
        dataIndex: 'id',
        width: 50,
        items: utils.makeGridFilterTextField('id')
    }, {
        header: 'Nextility Account Number',
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
        flex: 1,
        items: utils.makeGridFilterTextField('service_address')
    }],
    dockedItems: [
    {
        xtype: 'toolbar',
        dock: 'bottom',
        items: ['->', {
            xtype: 'combo',
            name: 'accountsFilter',
            fieldLabel: 'Filter',
            labelWidth: 50,
            width: 400,
            value: 'none',
            editable: false,
            store: 'AccountsFilter',
            triggerAction: 'all',
            valueField: 'value',
            displayField: 'label',
            forceSelection: true,
            listeners:{
                scope: this,
                'select': function(combo, record, index) {
                    var g = combo.findParentByType('grid');
                    g.getStore().clearFilter();
                    if (combo.getValue() == 'enter_bills')
                        g.getStore().filter('bills_to_be_entered', true);
                    else if(combo.getValue() == 'entered_bills')
                        g.getStore().filter('bills_to_be_entered', false);
                }
            }
       }, '->']
    }]
});
