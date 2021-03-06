Ext.define('ReeBill.view.accounts.Accounts', {
    extend: 'Ext.grid.Panel',
    requires: [
        'ReeBill.store.AccountsFilter'],
    title: 'Accounts',
    alias: 'widget.accounts',   
    store: 'Accounts',
    selModel: {
      mode: 'MULTI'
    },

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


    dockedItems: [{
        dock: 'top',
        layout:{
            type:'hbox',
            align:'stretch'
        },
        items: [{
            xtype: 'button',
            itemId: 'createNewAccount',
            action: 'createAccount',
            text: 'New',
            iconCls: 'silk-add'
        },{
            xtype: 'button',
            itemId: 'editAccountRecord',
            action: 'editRecord',
            text: 'Edit',
            iconCls: 'silk-edit',
            disabled: true
        },{
            xtype: 'button',
            itemId: 'mergeAccountRecord',
            action: 'mergeRecords',
            text: 'Merge',
            iconCls: 'silk-merge',
            disabled: true
        },{
            xtype: 'combo',
            name: 'accountsFilter',
            fieldLabel: 'Filter',
            labelWidth: 30,
            width: 200,
            value: 'none',
            editable: false,
            store: 'AccountsFilter',
            triggerAction: 'all',
            valueField: 'value',
            displayField: 'label',
            forceSelection: true
        }]
    }]
});
