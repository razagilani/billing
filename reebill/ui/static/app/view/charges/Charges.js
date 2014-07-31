Ext.define('ReeBill.view.Charges', {
    extend: 'Ext.grid.Panel',

    requires: [
        'Ext.grid.feature.Grouping'
    ],

    title: 'Charges',
    alias: 'widget.charges',    
    store: 'Charges',
    preventHeader: true,

    
    plugins: [
        Ext.create('Ext.grid.plugin.CellEditing', {
            clicksToEdit: 2
        })
    ],

    features: [{
        ftype: 'grouping',
        groupHeaderTpl: 'Charge Group: {name} ({rows.length} Item{[values.rows.length > 1 ? "s" : ""]})',
        hideGroupedHeader: true
    }, {
        ftype: 'summary'
    }],

    viewConfig: {
        trackOver: false,
        stripeRows: true,
        getRowClass: function(record) {

        }
    },
    
    columns: [{
        header: 'RSI Binding',
        width: 200,
        sortable: true,
        dataIndex: 'rsi_binding',
        editor: {
            xtype: 'textfield',
            allowBlank: false
        }
    },{
        header: 'Description',
        width: 100,
        sortable: true,
        dataIndex: 'description'
    },{
        header: 'Quantity',
        width: 100,
        sortable: true,
        dataIndex: 'quantity'
    },{
        header: 'Units',
        width: 100,
        sortable: true,
        dataIndex: 'quantity_units',
        editor: {
            xtype: 'combo',
            name: 'units',
            store: 'Units',
            triggerAction: 'all',
            valueField: 'name',
            displayField: 'value',
            queryMode: 'local',
            forceSelection: true,
            selectOnFocus: true
        }  
    },{
        header: 'Rate',
        width: 100,
        sortable: true,
        dataIndex: 'rate'
    },{
        header: 'Total', 
        width: 100, 
        sortable: true, 
        dataIndex: 'total', 
        summaryType: 'sum',
        align: 'right',
        renderer: Ext.util.Format.usMoney
    }],

    dockedItems: [{
        dock: 'top',
        xtype: 'toolbar',
        items: [{
            xtype: 'button',
            text: 'Recompute All',
            action: 'recalculateAll',
            iconCls: 'silk-calculator'
        },{        
            xtype: 'button',
            text: 'Insert',
            action: 'newCharge',
            iconCls: 'silk-add',
            disabled: true
        },{        
            xtype: 'button',
            text: 'Remove',
            action: 'deleteCharge',
            iconCls: 'silk-delete',
            disabled: true
        },{        
            xtype: 'button',
            text: 'Add Group',
            action: 'addChargeGroup',
            iconCls: 'silk-add'
        },{        
            xtype: 'button',
            text: 'Regenerate from Rate Structure',
            action: 'regenerateFromRateStructure',
            iconCls: 'silk-wrench'
        }]
    }]
});