Ext.define('ReeBill.view.charges.Charges', {
    extend: 'Ext.grid.Panel',

    requires: [
        'Ext.grid.*',
        'Ext.data.*',
        'Ext.dd.*',
        'ReeBill.view.charges.FormulaField',
        'ReeBill.view.charges.GroupTextField',
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
        header: 'Name',
        sortable: true,
        dataIndex: 'rsi_binding',
        editor: {
            xtype: 'textfield',
            allowBlank: false
        },
        width: 180
    },{
        header: 'Total',
        width: 110,
        sortable: true,
        dataIndex: 'target_total',
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
        //},{
        //    xtype: 'button',
        //    text: 'Regenerate',
        //    action: 'regenerateCharge',
        //    iconCls: 'silk-wrench'
        //},{
        //    xtype: 'button',
        //    text: 'Recompute',
        //    action: 'recomputeCharges'
        //},'-',{
        //    xtype: 'formulaField',
        //    name: 'formulaField'
        //},'-',{
        //    xtype: 'groupTextField',
        //    name: 'groupTextField'
        }]
    }]
});
