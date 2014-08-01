Ext.define('ReeBill.view.RateStructures', {
    extend: 'Ext.grid.Panel',

    requires: [
        'Ext.grid.*',
        'Ext.data.*',
        'Ext.dd.*'
    ],

    alias: 'widget.rateStructures',    
    store: 'RateStructures',
    preventHeader: true,
    
    plugins: [{
        ptype: 'cellediting',
        clicksToEdit: 2
    }],

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
        itemId: 'rateStructureGridView',
        getRowClass: function(record) {
            if (record.get('error')){
                return 'ratestructure-grid-error';
            }
        },
        plugins:[{
            ptype: 'gridviewdragdrop',
        }],
        listeners: {
            drop: function(node, data, overModel, dropPosition, eOpts) {
                data.records[0].set('group', overModel.get('group'));
            }
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
        xtype: 'templatecolumn',
        header: 'Quantity',
        id: 'quantity',
        sortable: true,
        dataIndex: 'quantity_formula',
        editor: {
            xtype: 'textfield',
            allowBlank: false
        },
        flex: 1,
        width: 250,
        tpl: '{[values.error ? values.error : values.quantity]}'
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
        xtype: 'templatecolumn',
        header: 'Rate',
        sortable: true,
        dataIndex: 'rate_formula',
        editor: {
            xtype: 'textfield',
            allowBlank: false
        },
        flex: 1,
        width: 250,
        allowBlank: false,
        tpl: '{[values.error ? values.error : values.rate]}'
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
        },'-',{
            xtype: 'groupTextField',
            name: 'groupTextField'
        },'-',{
            xtype: 'roundRuleTextField',
            name: 'roundRuleTextField'
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