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
        function deepcopy(x){
            // this is the fastest way to deepcopy an object in JS, but it will not copy
            // complex datatypes and functions
            return JSON.parse(JSON.stringify(x));
        }

        // Copy all individual columns and fold quantity into quantity_formula
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
            }else if(this.columns[i]['dataIndex'] === 'total'){
                var col = deepcopy(this.columns[i]);
                // We have to explicityly redefine the summary function here, since
                // deepcopy cannot do that. We have to redefine because ExtJS does
                // something weird with the function, so assigning the parents
                // reference will not work
                col.summaryType = function(records){
                    var sum = 0;
                    Ext.Array.each(records, function(record){
                        if(record.get('has_charge')){
                            sum += record.get('total');
                        }
                    });
                    return Ext.util.Format.usMoney(sum);
                };
                newColumns.push(col);
            }else if(this.columns[i]['dataIndex'] !== 'quantity'){
                newColumns.push(deepcopy(this.columns[i]));
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