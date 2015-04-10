Ext.define('ReeBill.view.issuablereebills.IssuableReebills', {
    extend: 'Ext.grid.Panel',

    requires: [
        'Ext.grid.feature.Grouping',
        'Ext.toolbar.PagingMemoryToolbar'
    ],

    title: 'Issuable Reebills',
    alias: 'widget.issuableReebills',
    multiSelect: true,
    store: 'IssuableReebillsMemory',
    
    plugins: [
        Ext.create('Ext.grid.plugin.CellEditing', {
            clicksToEdit: 2
        })
    ],

    features: [{
        ftype: 'groupingsummary',
        hideGroupedHeader: true
    }],

    viewConfig: {
        trackOver: false,
        stripeRows: true,
        getRowClass: function(record) {

        }
    },
    
    columns: [{
        header: 'Account',
        dataIndex: 'account',
        width: 90,
        sortable: true
    },{
        header: 'Sequence',
        dataIndex: 'sequence',
        width: 90,
        sortable: true
    },{
        header: 'Recipients',
        sortable: false,
        groupable: false,
        dataIndex: 'mailto',
        minWidth: 175,
        flex: 1,
        editor: {
            xtype: 'textfield'
        },
        renderer: function(val) {
            if (!val)
                return "<i>Enter a recipient for this bill before issuing</i>";

            return val;
        }
    },{
        header: 'Total From Utility Bill',
        dataIndex: 'utilbill_total',
        width: 130,
        sortable: true,
        renderer: Ext.util.Format.usMoney
    },{
        header: 'Computed Total',
        dataIndex: 'actual_total',
        width: 130,
        sortable: true,
        renderer: Ext.util.Format.usMoney
    },{
        header: '$ Difference',
        dataIndex: 'difference',
        width: 130,
        sortable: true,
        align: 'right',
        renderer: Ext.util.Format.usMoney
    },{
        header: 'Adjustment',
        dataIndex: 'adjustment',
        width: 175,
        sortable: true,
        renderer: Ext.util.Format.usMoney
        },{
        xtype: 'checkcolumn',
        text: 'Processed',
        disabled: true,
        dataIndex: 'processed'
    }],

    dockedItems: [{
        dock: 'top',
        xtype: 'toolbar',
        layout: {
            overflowHandler: 'Menu'
        },
        items: [{        
            xtype: 'button',
            text: 'Issue Selected ReeBills',
            action: 'issue',
            iconCls: 'silk-email-go',
            disabled: true
        },{
            xtype: 'button',
            text: 'Issue All Processed ReeBills',
            action: 'issueprocessed',
            iconCls: 'silk-email-go'
        },{
            xtype: 'button',
            text: 'Summary For Selected Bills',
            action: 'createsummaryforselectedbills',
            disabled: true,
            iconCls: 'silk-application-go'
        },{
            xtype: 'button',
            text: 'Summary Of Bills For Selected Tag',
            action: 'createsummaryfortag',
            disabled: true,
            iconCls: 'silk-application-go'
        },'-',{
            xtype: 'combo',
            fieldLabel: 'Filter Bills on Tags',
            store: 'CustomerGroups',
            displayField: 'name',
            valueField: 'id',
            itemId: 'filter_bills_combo'
        }]
    }]

});
