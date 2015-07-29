Ext.define('ReeBill.view.accounts.Accounts', {
    extend: 'Ext.grid.Panel',
    requires: [
        'ReeBill.store.AccountsFilter'],
    title: 'Accounts Processing Status',
    alias: 'widget.accounts',   
    store: 'Accounts',

    plugins: [
        Ext.create('Ext.grid.plugin.CellEditing', {
            clicksToEdit: 2
        }),
        {
            ptype: 'bufferedrenderer',
            trailingBufferZone: 20,  // Keep 20 rows rendered in the table behind scroll
            leadingBufferZone: 50   // Keep 50 rows rendered in the table ahead of scroll
        }
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
        header: 'Account',
        dataIndex: 'account',
        width: 100,
        items: utils.makeGridFilterTextField('account')
    },{
        header: 'Tags',
        dataIndex: 'tags',
        editor: {
            xtype: 'textfield',
            emptyText: 'Enter comma-separated list'
        },
        tdCls: 'grid-cell-wrap-text',
        width: 150,
        items: utils.makeGridFilterTextField('tags'),
        renderer: function(value){
            var rtn = [];
            Ext.Array.each(value.split(','), function(tag){
                tag = tag.trim();
                if(tag){
                    rtn.push('<span class="accounts-tag">');
                    rtn.push(tag);
                    rtn.push('</span>');
                }
            });
            return rtn.join('')
        }
    },{
        header: 'Utility Account Number',
        dataIndex: 'utility_account_number',
        editor: {
            xtype: 'textfield'
        },
        width: 100,
        items: utils.makeGridFilterTextField('utility_account_number')
    },{
        header: 'Remit To',
        dataIndex: 'payee',
        editor:{
            xtype: 'textfield'
        },
        width: 120,
        items: utils.makeGridFilterTextField('payee')
    },{
        header: 'Codename',
        dataIndex: 'codename',
        width: 120,
        items: utils.makeGridFilterTextField('codename')
    },{
        header: 'Casual Name',
        dataIndex: 'casualname',
        width: 200,
        items: utils.makeGridFilterTextField('casualname')
    },{
        header: 'Primus Name',
        dataIndex: 'primusname',
        width: 120,
        items: utils.makeGridFilterTextField('primusname')
    },{
        header: 'Utility Service Address',
        dataIndex: 'utilityserviceaddress',
        width: 200,
        items: utils.makeGridFilterTextField('utilityserviceaddress')
    },{
        header: 'Last Event',
        dataIndex: 'lastevent',
        minWidth: 350,
        flex:1,
        items: utils.makeGridFilterTextField('lastevent')
    }],
    dockedItems: [
    {
        dock: 'top',
        xtype: 'toolbar',
        layout: {
            overflowHandler: 'Menu'
        },
        items: [{
            xtype: 'button',
            itemId: 'editAccountRecord',
            action: 'editRecord',
            text: 'Edit',
            iconCls: 'silk-edit',
            disabled: true
        }]
    },
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
                    if (combo.getValue() == 'reebillcustomers')
                        g.getStore().filter('reebill_customer', true);
                    else if(combo.getValue() == 'brokeragecustomers')
                        g.getStore().filter('brokerage_account', true);
                }
            }
            }, '->']
    }]
});
