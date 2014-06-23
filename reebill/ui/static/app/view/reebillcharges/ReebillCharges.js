Ext.define('ReeBill.view.ReebillCharges', {
    extend: 'Ext.grid.Panel',

    requires: [
        'Ext.grid.feature.Grouping'
    ],

    title: 'Reebill Charges',
    alias: 'widget.reebillCharges',    
    store: 'ReebillCharges',
    
    plugins: [
        Ext.create('Ext.grid.plugin.CellEditing', {
            clicksToEdit: 2
        })
    ],

    features: [{
        ftype: 'groupingsummary',
        groupHeaderTpl: 'Charge Group: {name} ({rows.length} Item{[values.rows.length > 1 ? "s" : ""]})',
        hideGroupedHeader: true
    }],

    viewConfig: {
        trackOver: false,
        stripeRows: true,
        getRowClass: function(record) {

        }
    },
    
    columns: [{
        header: 'RSI Binding',
        dataIndex: 'rsi_binding',
        width: 150
    },{
        header: 'Description',
        dataIndex: 'description',
        width: 150
    },{
        header: 'Actual Quantity',
        dataIndex: 'actual_quantity'
    },{
        header: 'Hypo Quantity',
        dataIndex: 'quantity'
    },{
        header: 'Units',
        dataIndex: 'quantity_units'
    },{
        header: 'Actual Rate',
        dataIndex: 'actual_rate'
    },{
        header: 'Hypo Rate',
        dataIndex: 'rate'
    },{
        header: 'Actual Total', 
        dataIndex: 'actual_total',
        align: 'right',
        summaryType: 'sum',
        summaryRenderer: function(value) { return '<b>' + Ext.util.Format.usMoney(value) + '</b>'},
        renderer: Ext.util.Format.usMoney
    },{
        header: 'Hypo Total', 
        dataIndex: 'total',
        align: 'right',
        summaryType: 'sum',
        summaryRenderer: function(value) { return '<b>' + Ext.util.Format.usMoney(value) + '</b>'},
        renderer: Ext.util.Format.usMoney
    }]
});