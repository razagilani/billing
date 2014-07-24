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

    viewConfig: {
        trackOver: false,
        stripeRows: true,
        getRowClass: function(record) {

        }
    },
    
    columns: [{
        header: 'Shared',
        dataIndex: 'shared',
        sortable: true,
        width: 60,
        renderer: checkboxRenderer
    },{
        header: 'RSI Binding',
        sortable: true,
        dataIndex: 'rsi_binding',
        editor: {
            xtype: 'textfield',
            allowBlank: false
        },
        width: 150
    },{
        header: 'Description',
        sortable: true,
        dataIndex: 'description',
        editor: {
            xtype: 'textfield',
            allowBlank: false
        }
    },{
        header: 'Quantity',
        id: 'quantity',
        sortable: true,
        dataIndex: 'quantity',
        editor: {
            xtype: 'textfield',
            allowBlank: false
        },
        width: 250
    },{
        header: 'Units',
        sortable: true,
        dataIndex: 'quantity_units',
        editor: {
            xtype: 'textfield',
            allowBlank: false
        },
        width: 50
    },{
        header: 'Rate',
        sortable: true,
        dataIndex: 'rate',
        editor: {
            xtype: 'textfield',
            allowBlank: false
        },
        width: 75,
        allowBlank: false
    },{
        header: 'Round Rule',
        sortable: true,
        dataIndex: 'round_rule',
        editor: {
            xtype: 'textfield',
            allowBlank: false
        },
        width: 100
    },{
        header: 'Has Charge',
        dataIndex: 'has_charge',
        sortable: true,
        width: 80,
        renderer: checkboxRenderer
    },{
        header: 'Group',
        dataIndex: 'group',
        sortable: true,
        editor: {
            xtype: 'textfield',
            allowBlank: false
        },
       width: 60
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