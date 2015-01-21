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
        editor: {
            xtype: 'numberfield',
            allowBlank: false,
            step: 0.01
        },
        summaryType: function(records){
            var sum = 0;
            Ext.Array.each(records, function(record){
                sum += record.get('target_total');
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
