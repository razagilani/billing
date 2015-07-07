Ext.define('ReeBill.view.charges.Charges', {
    extend: 'ReeBill.view.charges.PreviousCharges',


    requires: [
        'Ext.grid.*',
        'Ext.data.*',
        'Ext.dd.*',
        'ReeBill.view.charges.FormulaField',
        'ReeBill.view.charges.RoundRuleTextField'
    ],

    alias: 'widget.charges',
    title: "This Bill's Charges",

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