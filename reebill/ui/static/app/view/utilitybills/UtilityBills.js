Ext.define('ReeBill.view.utilitybills.UtilityBills', {
    extend: 'Ext.grid.Panel',
    requires: [
        'Ext.toolbar.PagingMemoryToolbar',
        'ReeBill.store.Suppliers',
        'ReeBill.store.Services',
        'ReeBill.store.Utilities',
        'ReeBill.store.RateClasses'
    ],
    title: 'Utility Bills',
    alias: 'widget.utilityBills',    
    store: 'UtilityBillsMemory',
    
    plugins: [
        Ext.create('Ext.grid.plugin.CellEditing', {
            clicksToEdit: 2,
            listeners: {
                beforeedit: function (e, editor) {
                    if (editor.record.get('processed'))
                        return false;
                }
            }
        })
    ],

    viewConfig: {
        trackOver: false,
        stripeRows: true,
        getRowClass: function(record) {
            if (!record.get('processed'))
                return 'utilbill-grid-unprocessed';
        }
    },
    
    columns: [{
        header: 'Name',
        dataIndex: 'name',
        hidden: true
    },{
        header: 'Service',
        dataIndex: 'service',
        width: 100
    },{
        header: 'Start Date',
        dataIndex: 'period_start',
        editor: {
            xtype: 'datefield',
            allowBlank: false, 
            format: 'Y-m-d'
        },
        width: 100,
        renderer: function(value) {
            return Ext.util.Format.date(value, 'Y-m-d');
        }
    },{
        header: 'End Date',
        dataIndex: 'period_end',
        editor: {
            xtype: 'datefield',
            allowBlank: false, 
            format: 'Y-m-d'
        },
        width: 100,
        renderer: function(value) {
            return Ext.util.Format.date(value, 'Y-m-d');
        }
    },{
        header: 'Total',
        dataIndex: 'target_total',
        editor: {
            xtype: 'numberfield',
            allowBlank: false
        },
        width: 100,
        renderer: Ext.util.Format.usMoney
    },{
        header: 'Calculated',
        dataIndex: 'computed_total',
        width: 100,
        renderer: Ext.util.Format.usMoney
    },{
        header: 'RB Seq./Vers.',
        tooltip: 'Reebill Sequence/Version',
        dataIndex: 'reebills',
        width: 120,
        renderer: function(value, metaData, record) {
            var result = '';
            var reebills = record.get('reebills');

            for (var i = 0; i < reebills.length; i++) {
                var sequence = reebills[i].sequence;
                result += sequence.toString() + "-";
                while (i < reebills.length && reebills[i].sequence ==
                        sequence) {
                    result += reebills[i].version + ",";
                    i++;
                } 
                result = result.substr(0,result.length-1);
                result += ' ';
            }

            return result;
        }
    },{
        header: 'Processed',
        dataIndex: 'processed',
        width: 100,
        tooltip: "<b>Processed:</b> This bill's rate structure and charges are correct and will be used to predict the rate structures of other bills.<br /><b>Unprocessed:</b> This bill will be ingnored when predicting the rate structures of other bills.<br />",
        renderer: function(value) {
            return value ? 'Yes' : 'No';                    
        }
    },{
        header: 'State',
        dataIndex: 'state',
        width: 100
    },{
        header: 'Utility',
        dataIndex: 'utility',
        editor: {
            xtype: 'combo',
            store: 'Utilities',
            itemId: 'utility_combo',
            displayField: 'name',
            valueField: 'name',
            triggerAction: 'all',
            forceSelection: false,
            typeAhead: true,
            typeAheadDelay : 1,
            autoSelect: false,
            regex: /[a-zA-Z0-9]+/,
            minChars: 1
        },
        width: 150,
        renderer: function(value, metaData, record) {
            return record.get('utility').name;
        }
    },{
        header: 'Rate Class',
        dataIndex: 'rate_class_id',
        emptyText: 'Unknown Rate Class',
        editor: {
            xtype: 'combo',
            store: 'RateClasses',
            itemId: 'rate_class_combo',
            displayField: 'name',
            valueField: 'id',
            triggerAction: 'all',
            forceSelection: false,
            typeAhead: true,
            typeAheadDelay: 1,
            autoSelect: false,
            regex: /[a-zA-Z0-9]+/,
            minChars: 1
        },
        minWidth: 250,
        flex: 1,
        renderer: function(val, metaDate, record){
            return record.get('rate_class');
        }
    },{
        header: 'Supplier',
        dataIndex: 'supplier_id',
        emptyText: 'Unknown Supplier',
        editor: {
            xtype: 'combo',
            store: 'Suppliers',
            itemId: 'supplier_combo',
            displayField: 'name',
            valueField: 'id',
            triggerAction: 'all',
            forceSelection: false,
            typeAhead: true,
            typeAheadDelay : 1,
            autoSelect: false,
            regex: /[a-zA-Z0-9]+/,
            minChars: 1
        },
        width: 150,
        renderer: function(value, metaData, record) {
            return record.get('supplier').name;
        }
    },{
        header: 'Supply Group',
        dataIndex: 'supply_group',
        emptyText: 'Unknown Supply Group',
        editor: {
            xtype: 'combo',
            store: 'SupplyGroups',
            itemId: 'supply_group_combo',
            displayField: 'name',
            valueField: 'name',
            triggerAction: 'all',
            forceSelection: false,
            typeAhead: true,
            typeAheadDelay: 1,
            autoSelect: false,
            regex: /[a-zA-Z0-9]+/,
            minChars: 1
        },
        minWidth: 250,
        flex: 1
    }],

    dockedItems: [{
        dock: 'top',
        xtype: 'toolbar',
        layout: {
            overflowHandler: 'Menu'
        },
        items: [{
            xtype: 'button',
            action: 'utilbillCompute',
            text: 'Compute',
            disabled: true
        },{
            xtype: 'button',
            action: 'utilbillRemove',
            iconCls: 'silk-delete',
            text: 'Delete',
            disabled: true
        },{
            xtype: 'button',
            action: 'utilbillToggleProcessed',
            text: 'Toggle Processed',
            disabled: true
//        },'-',{
//            xtype: 'button',
//            action: 'utilbillDla',
//            text: 'Layout',
//            disabled: true
//        },{
//            xtype: 'button',
//            action: 'utilbillSlice',
//            text: 'Identify',
//            disabled: true
//        },{
//            xtype: 'button',
//            action: 'utilbillResults',
//            text: 'Review',
//            disabled: true
        }]
    }],

    bbar: {
        xtype: 'pagingmemorytoolbar',
        pageSize: 25,
        store: 'UtilityBillsMemory',
        refreshStore: 'UtilityBills',
        displayInfo: true,
        displayMsg: 'Displaying {0} - {1} of {2}'
    }
});
