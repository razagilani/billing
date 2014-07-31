Ext.define('ReeBill.view.RateStructures', {
    extend: 'Ext.grid.Panel',

    alias: 'widget.rateStructures',    
    store: 'RateStructures',
    preventHeader: true,
    
    plugins: [
        Ext.create('Ext.grid.plugin.CellEditing', {
            clicksToEdit: 2
        })
    ],

    features: [{
        ftype: 'summary'
    }],

    viewConfig: {
        trackOver: false,
        stripeRows: true,
        getRowClass: function(record) {

        }
    },

    forceFit: true,
    
    columns: [{
        header: 'Shared',
        dataIndex: 'shared',
        sortable: true,
        width: 65,
        flex: 0,
        renderer: checkboxRenderer
    },{
        header: 'RSI Binding',
        sortable: true,
        dataIndex: 'rsi_binding',
        editor: {
            xtype: 'textfield',
            allowBlank: false
        },
        width: 180,
        flex: 0
    },{
        header: 'Description',
        sortable: true,
        dataIndex: 'description',
        editor: {
            xtype: 'textfield',
            allowBlank: false
        },
        flex: 0,
        width: 150
    },{
        header: 'Quantity',
        id: 'quantity',
        sortable: true,
        dataIndex: 'quantity',
        editor: {
            xtype: 'textfield',
            allowBlank: false
        },
        flex: 1,
        width: 250
    },{
        header: 'Units',
        sortable: true,
        dataIndex: 'quantity_units',
        editor: {
            xtype: 'textfield',
            allowBlank: false
        },
        flex: 0,
        width: 70
    },{
        header: 'Rate',
        sortable: true,
        dataIndex: 'rate',
        editor: {
            xtype: 'textfield',
            allowBlank: false
        },
        flex: 1,
        width: 250,
        allowBlank: false
    },{
        header: 'Round Rule',
        sortable: true,
        dataIndex: 'round_rule',
        editor: {
            xtype: 'textfield',
            allowBlank: false
        },
        flex: 0,
        width: 100
    },{
        header: 'Has Charge',
        dataIndex: 'has_charge',
        sortable: true,
        width: 100,
        renderer: checkboxRenderer
    },{
        header: 'Group',
        dataIndex: 'group',
        sortable: true,
        editor: {
            xtype: 'textfield',
            allowBlank: false
        },
        flex: 0,
        width: 90
    },{
        header: 'Total',
        width: 90,
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
            text: 'Insert',
            action: 'newRateStructure',
            iconCls: 'silk-add'
        },{        
            xtype: 'button',
            text: 'Remove',
            action: 'removeRateStructure',
            iconCls: 'silk-delete',
            disabled: true
        },{
            xtype: 'button',
            text: 'Regenerate',
            action: 'regenerateRateStructure',
            iconCls: 'silk-wrench'
        },'-',{
        xtype: 'formulaField',
        name: 'formulaField',
        }]
    }]
});

/**
 * Renders a checkbox 
 */
function checkboxRenderer(val) {
    if (val)
        return '<div style="text-align: center;"><img class="x-grid-checkcolumn x-grid-checkcolumn-checked" src="data:image/gif;;base64,R0lGODlhAQABAID/AMDAwAAAACH5BAEAAAAALAAAAAABAAEAAAICRAEAOw=="></div>';

    return '<div style="text-align: center;"><img class="x-grid-checkcolumn" src="data:image/gif;;base64,R0lGODlhAQABAID/AMDAwAAAACH5BAEAAAAALAAAAAABAAEAAAICRAEAOw=="></div>';
}