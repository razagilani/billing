Ext.define('ReeBill.view.charges.Charges', {
    extend: 'Ext.grid.Panel',

    requires: [
        'Ext.grid.*',
        'Ext.data.*',
        'Ext.dd.*',
        'ReeBill.view.charges.FormulaField',
        'ReeBill.view.charges.RoundRuleTextField'
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
        hideGroupedHeader: false
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
                if (overModel.store.groupers.keys.length > 0){
                    var groupByField = overModel.store.groupers.keys[0];
                    Ext.Array.each(data.records, function(record){
                        record.set(groupByField, overModel.get(groupByField));
                    });
                    Ext.getStore('Charges').group(groupByField, 'ASC');
                }
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
        width: 90
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
            return sum;
        },
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
        }]
    }]
});