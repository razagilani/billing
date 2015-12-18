Ext.define('ReeBill.view.charges.PreviousCharges', {
    extend: 'Ext.grid.Panel',

    alias: 'widget.previouscharges',
    title: "Previous Bill's Charges",
    titleCollapse: true,
    
    features: [{
        ftype: 'groupingsummary',
        groupHeaderTpl: 'Charge Group: {name} ({rows.length} Item{[values.rows.length > 1 ? "s" : ""]})',
        hideGroupedHeader: false
    }, {
        ftype: 'summary'
    }],

    viewConfig: {
        trackOver: false,
        stripeRows: true,
        enableTextSelection: true,
    },

    forceFit: true,
    
    columns: [{
        // To fix BILL-6254 where entering a space in any text field toggled
        // the flagged field on/off in the utility bills tab of reebill
        // This was due to a bug in Extjs 4.2.3 where Space pressed in grid
        // cell editor fires first column action in first cell
        // See the bug in Extjs 4.2.3 below http://www.sencha.com/forum/showthread.php?296487
        header: 'hidden',
        editor: {
            xtype: 'textfield',
            allowBlank: true,
            editable: false
        },
        hidden: true
    },{
        xtype: 'checkcolumn',
        header: 'Shared',
        dataIndex: 'shared',
        sortable: true,
        width: 65,
        disabled:true
    },{
        header: 'RSI Binding',
        sortable: true,
        dataIndex: 'rsi_binding',
        editor: {
            xtype: 'combo',
            store: 'RSIBindings',
            allowBlank: false,
            minChars: 1,
            typeAhead: true,
            triggerAction: 'all',
            valueField: 'name',
            displayField: 'name',
            forceSelection: true,
            selectOnFocus: true
        },
        width: 180,
        disabled:true
    },{
        header: 'Description',
        sortable: true,
        dataIndex: 'description',
        editor: {
            xtype: 'textfield',
            allowBlank: false
        },
        width: 150,
        disabled:true
    },{
        header: 'Quantity Formula',
        itemId: 'quantityFormula',
        sortable: true,
        dataIndex: 'quantity_formula',
        flex: 1,
        width: 250,
        disabled:true
    },{
        header: 'Quantity',
        itemId: 'quantity',
        sortable: true,
        dataIndex: 'quantity',
        width: 100,
        disabled:true
    },{
        header: 'Units',
        sortable: true,
        dataIndex: 'unit',
        editor: {
            xtype: 'combo',
            store: 'Units',
            allowBlank: false,
            minChars: 1,
            typeAhead: true,
            triggerAction: 'all',
            valueField: 'value',
            displayField: 'name',
            queryMode: 'local',
            forceSelection: true,
            selectOnFocus: true
        },
        width: 70,
        disabled:true
    },{
        header: 'Rate',
        sortable: true,
        dataIndex: 'rate',
        editor: {
            xtype: 'textfield',
            allowBlank: false
        },
        width: 100,
        allowBlank: false,
        disabled:true
    },{
        xtype: 'checkcolumn',
        header: 'Has Charge',
        dataIndex: 'has_charge',
        sortable: true,
        width: 100,
        disabled:true
    },{
        header: 'Type',
        dataIndex: 'type',
        sortable: true,
        editor: {
            xtype: 'combo',
            store: 'Types',
            allowBlank: false,
            minChars: 1,
            typeAhead: true,
            triggerAction: 'all',
            valueField: 'value',
            displayField: 'name',
            queryMode: 'local',
            forceSelection: true
        },
        width: 90,
        disabled:true
    },{
        header: 'Total',
        width: 110,
        sortable: true,
        dataIndex: 'total',
        summaryType: function(records){
            var sum = 0;
            Ext.Array.each(records, function(record){
                if(record.get('has_charge')){
                    sum += record.get('total');
                }
            });
            return Ext.util.Format.usMoney(sum);
        },
        align: 'right',
        renderer: Ext.util.Format.usMoney,
        disabled:true
    }]
});