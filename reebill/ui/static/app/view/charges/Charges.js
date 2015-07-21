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

    initComponent: function(){
        // Combine the quantity_formula & formula columns into on single column
        var newColumns = [];
        for(var i =0; i<this.columns.length; i++){
            if (this.columns[i]['dataIndex'] === 'quantity_formula') {
                newColumns.push({
                    xtype: 'templatecolumn',
                    header: 'Quantity',
                    itemId: 'quantity',
                    sortable: true,
                    dataIndex: 'quantity_formula',
                    editor: {
                        xtype: 'textfield',
                        allowBlank: true
                    },
                    flex: 1,
                    width: 250,
                    tpl: '{[values.error ? values.error : values.quantity]}'
                });
            }else if(this.columns[i]['dataIndex'] !== 'quantity'){
                // Fastest way to deep copy
                newColumns.push(JSON.parse(JSON.stringify(this.columns[i])));
            }
        }

        // Enable all columns
        for (var i = 0; i < newColumns.length; i++) {
            newColumns[i].disabled = false;
        }

        this.columns = newColumns;
        this.callParent(arguments);
    },

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