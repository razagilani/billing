Ext.define('ReeBill.view.Charges', {
    extend: 'Ext.grid.Panel',

    requires: [
        'Ext.grid.*',
        'Ext.data.*',
        'Ext.dd.*'
    ],

    alias: 'widget.charges',
    store: 'Charges',
    preventHeader: true,
    
    plugins: [{
        ptype: 'cellediting',
        clicksToEdit: 2
    }],

    features: [{
        ftype: 'groupingsummary',
        groupHeaderTpl: 'Charge Group: {name} ({rows.length} Item{[values.rows.length > 1 ? "s" : ""]})',
        hideGroupedHeader: true
    }, {
        ftype: 'summary'
    }],

    viewConfig: {
        trackOver: false,
        stripeRows: true,
        itemId: 'chargesGridView',
        getRowClass: function(record) {
            if (record.get('error')){
                return 'charges-grid-error';
            }
        },
        plugins:[{
            ptype: 'gridviewdragdrop'
        }],
        listeners: {
            drop: function(node, data, overModel, dropPosition, eOpts) {
                data.records[0].set('group', overModel.get('group'));
                Ext.getStore('Charges').group('group', 'ASC');
            }
        }
    },

    forceFit: true,
    
    columns: [{
        xtype: 'checkcolumn',
        header: 'Shared',
        dataIndex: 'shared',
        sortable: true,
        width: 65
    },{
        header: 'RSI Binding',
        sortable: true,
        dataIndex: 'rsi_binding',
        editor: {
            xtype: 'textfield',
            allowBlank: false
        },
        width: 180
    },{
        header: 'Description',
        sortable: true,
        dataIndex: 'description',
        editor: {
            xtype: 'textfield',
            allowBlank: false
        },
        width: 150
    },{
        xtype: 'templatecolumn',
        header: 'Quantity',
        id: 'quantity',
        sortable: true,
        dataIndex: 'quantity_formula',
        editor: {
            xtype: 'textfield',
            allowBlank: true
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
        xtype: 'checkcolumn',
        header: 'Has Charge',
        dataIndex: 'has_charge',
        sortable: true,
        width: 100
    },{
        header: 'Group',
        dataIndex: 'group',
        sortable: true,
        editor: {
            xtype: 'textfield',
            allowBlank: false
        },
        width: 90
    },{
        header: 'Total',
        width: 110,
        sortable: true,
        dataIndex: 'total',
        summaryType: 'sum',
        align: 'right',
        renderer: Ext.util.Format.usMoney
    }],

    dockedItems: [{
        dock: 'top',
        xtype: 'toolbar',
        layout: {
            overflowHandler: 'Menu'
        },
        items: [{
            xtype: 'button',
            text: 'Insert',
            action: 'newCharge',
            iconCls: 'silk-add'
        },{        
            xtype: 'button',
            text: 'Remove',
            action: 'removeCharge',
            iconCls: 'silk-delete',
            disabled: true
        },{
            xtype: 'button',
            text: 'Regenerate',
            action: 'regenerateCharge',
            iconCls: 'silk-wrench'
        },{
            xtype: 'button',
            text: 'Recompute',
            action: 'recomputeCharges'
        },'-',{
            xtype: 'formulaField',
            name: 'formulaField'
        },'-',{
            xtype: 'groupTextField',
            name: 'groupTextField'
        }]
    }]
});