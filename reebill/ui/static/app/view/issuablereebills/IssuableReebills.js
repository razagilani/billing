Ext.define('ReeBill.view.IssuableReebills', {
    extend: 'Ext.grid.Panel',

    requires: [
        'Ext.grid.feature.Grouping'
    ],

    title: 'Issuable Reebills',
    alias: 'widget.issuableReebills',    
    store: 'IssuableReebills',
    
    plugins: [
        Ext.create('Ext.grid.plugin.CellEditing', {
            clicksToEdit: 2
        })
    ],

    features: [{
        ftype: 'groupingsummary',
        groupHeaderTpl: '{[values.children[0].get("matching")==true?"Reebill"+(values.rows.length>1?"s":"")+" with Matching Totals":"Reebill"+(values.rows.length>1?"s":"")+" without Matching Totals"]}',
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
        width: 120,
        sortable: true
    },{
        header: 'Sequence',
        dataIndex: 'sequence',
        width: 120,
        sortable: false
    },{
        header: 'Recipients',
        sortable: false,
        groupable: false,
        dataIndex: 'mailto',
        width: 250,
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
        dataIndex: 'util_total',
        width: 175,
        sortable: false,
        renderer: Ext.util.Format.usMoney
    },{
        header: 'Computed Total',
        dataIndex: 'reebill_total',
        width: 175,
        sortable: false,
        renderer: Ext.util.Format.usMoney
    },{
        header: '$ Difference',
        dataIndex: 'difference',
        width: 175,
        sortable: true,
        groupable: false,
        align: 'right',
        renderer: function(v, params, record) {
            return Ext.util.Format.usMoney(record.data.util_total - record.data.reebill_total);
        },
    }],

    dockedItems: [{
        dock: 'top',
        xtype: 'toolbar',
        items: [{        
            xtype: 'button',
            text: 'Issue',
            action: 'issue',
            iconCls: 'silk-email-go',
            disabled: true
        }]
    }],

    bbar: {
        xtype: 'pagingtoolbar',
        pageSize: 25,
        store: 'IssuableReebills',
        displayInfo: true,
        displayMsg: 'Displaying {0} - {1} of {2}'
    }

});