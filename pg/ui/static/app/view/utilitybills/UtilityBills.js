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
        header: 'Start',
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
        header: 'End',
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
        header: 'Energy',
        dataIndex: 'total_energy',
        editor: {
            xtype: 'numberfield',
            allowBlank: false
        },
        width: 100,
    },{
        header: 'Total',
        dataIndex: 'target_total',
        editor: {
            xtype: 'numberfield',
            allowBlank: false
        },
        width: 100,
        renderer: Ext.util.Format.usMoney
    }, {
        header: 'Service Address',
        dataIndex: 'service_address'
        },{
            header: 'Next Meter Read',
            dataIndex: 'next_estimated_meter_read_date'
        },{
            header: 'Total Supply',
            dataIndex: 'supply_total'
        },{
            header: 'Utility Account Number',
            dataIndex: 'utility_account_number'
        },{
            header: 'Secondary Utility Account Number',
            dataIndex: 'secondary_account_number'
    }, {
        header: 'Service',
        dataIndex: 'service',
        editor: {
            xtype: 'combo',
            name: 'service',
            store: 'Services',
            triggerAction: 'all',
            valueField: 'name',
            displayField: 'value',
            queryMode: 'local',
            forceSelection: true,
            selectOnFocus: true
        }
    },{
        header: 'Rate Class',
        dataIndex: 'rate_class',
        emptyText: 'Unknown Rate Class',
        editor: {
            xtype: 'combo',
            store: 'RateClasses',
            itemId: 'rate_class_combo',
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
        width: 125,
        flex: 1
    }
        //},{
        //    header: 'Utility',
        //    dataIndex: 'utility',
        //    editor: {
        //        xtype: 'combo',
        //        store: 'Utilities',
        //        itemId: 'utility_combo',
        //        displayField: 'name',
        //        valueField: 'name',
        //        triggerAction: 'all',
        //        forceSelection: false,
        //        typeAhead: true,
        //        typeAheadDelay : 1,
        //        autoSelect: false,
        //        regex: /[a-zA-Z0-9]+/,
        //        minChars: 1
        //    },
        //    width: 100,
        //    renderer: function(value, metaData, record) {
        //        return record.get('utility').name;
        //    }
        //},{
        //    header: 'Supplier',
        //    dataIndex: 'supplier',
        //    emptyText: 'Unknown Supplier',
        //    editor: {
        //        xtype: 'combo',
        //        store: 'Suppliers',
        //        itemId: 'supplier_combo',
        //        displayField: 'name',
        //        valueField: 'name',
        //        triggerAction: 'all',
        //        forceSelection: false,
        //        typeAhead: true,
        //        typeAheadDelay : 1,
        //        autoSelect: false,
        //        regex: /[a-zA-Z0-9]+/,
        //        minChars: 1
        //    },
        //    width: 100
    ],

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
            disabled: false,
        },{
            xtype: 'button',
            action: 'utilbillToggleProcessed',
            text: 'Toggle Processed',
            disabled: true
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
