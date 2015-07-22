Ext.define('ReeBill.view.accounts.Accounts', {
    extend: 'Ext.grid.Panel',
    requires: [
        'ReeBill.store.AccountsMemory',
        'ReeBill.store.AccountsFilter',
        'Ext.toolbar.PagingMemoryToolbar'],
    title: 'Accounts Processing Status',
    alias: 'widget.accounts',   
    store: 'AccountsMemory',
    selModel: {
      mode: 'MULTI'
    },

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
        header: 'Account',
        dataIndex: 'account',
        width: 100
    },{
        header: 'Tags',
        dataIndex: 'tags',
        editor: {
            xtype: 'textfield',
            emptyText: 'Enter comma-separated list'
        },
        tdCls: 'grid-cell-wrap-text',
        width: 150,
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
        width: 100
    },{
        header: 'Remit To',
        dataIndex: 'payee',
        editor:{
            xtype: 'textfield'
        },
        width: 120
    },{
        header: 'Codename',
        dataIndex: 'codename',
        width: 120
    },{
        header: 'Casual Name',
        dataIndex: 'casualname',
        width: 200
    },{
        header: 'Primus Name',
        dataIndex: 'primusname',
        width: 120
    },{
        header: 'Utility Service Address',
        dataIndex: 'utilityserviceaddress',
        width: 200
    },{
        header: 'Last Event',
        dataIndex: 'lastevent',
        minWidth: 350,
        flex:1
    },{
        header: 'Name',
        dataIndex: 'name',
        hidden: true,
        hideable: false
    },{
        header: 'Billing Addressee',
        dataIndex: 'ba_addressee',
        hidden: true,
        hideable: false
    },{
        header: 'Billing City',
        dataIndex: 'ba_city',
        hidden: true,
        hideable: false
    },{
        header: 'Billing Postal Code',
        dataIndex: 'ba_postal_code',
        hidden: true,
        hideable: false
    },{
        header: 'Billing State',
        dataIndex: 'ba_state',
        hidden: true,
        hideable: false
    },{
        header: 'Billing Street',
        dataIndex: 'ba_street',
        hidden: true,
        hideable: false
    },{
        header: 'Discount Rate',
        dataIndex: 'discount_rate',
        hidden: true,
        hideable: false
    },{
        header: 'Late Charge Rate',
        dataIndex: 'late_charge_rate',
        hidden: true,
        hideable: false
    },{
        header: 'Service Addressee',
        dataIndex: 'sa_addressee',
        hidden: true,
        hideable: false
    },{
        header: 'Service City',
        dataIndex: 'sa_city',
        hidden: true,
        hideable: false
    },{
        header: 'Service Postal Code',
        dataIndex: 'sa_postal_code',
        hidden: true,
        hideable: false
    },{
        header: 'Service State',
        dataIndex: 'sa_state',
        hidden: true,
        hideable: false
    },{
        header: 'Service Street',
        dataIndex: 'sa_street',
        hidden: true,
        hideable: false
    },{
        header: 'Service Type',
        dataIndex: 'service_type',
        hidden: true,
        hideable: false
    },{
        header: 'Template Account',
        dataIndex: 'template_account',
        hidden: true,
        hideable: false
    }],

    bbar: {
        xtype: 'pagingmemorytoolbar',
        pageSize: 25,
        store: 'AccountsMemory',
        refreshStore: 'Accounts',
        displayInfo: true,
        displayMsg: 'Displaying {0} - {1} of {2}',
        items: ['->',{
            xtype: 'combo',
            name: 'accountsFilter',
            fieldLabel: 'Filter',
            labelWidth: 50,
            width: 400,
            value: '',
            editable: false,
            store: 'AccountsFilter',
            triggerAction: 'all',
            valueField: 'value',
            displayField: 'label',
            forceSelection: true
        }]
    },
    dockedItems: [{
        dock: 'top',
        xtype: 'toolbar',
        layout: {
            overflowHandler: 'Menu'
        },
        items: [{
            xtype: 'button',
            itemId: 'mergeAccountRecord',
            action: 'mergeRecords',
            text: 'Merge',
            iconCls: 'silk-merge',
            disabled: true
        }]
    }]
});
