Ext.define('BillEntry.view.utilitybills.UtilityBills', {
    extend: 'Ext.grid.Panel',
    alias: 'widget.utilityBills',
    store: 'UtilityBills',
    
    plugins: [
        Ext.create('Ext.grid.plugin.CellEditing', {
            clicksToEdit: 2,
            listeners: {
                beforeedit: function (e, editor) {
                    if (editor.record.get('processed') || editor.record.get('entered')) {
                        Ext.MessageBox.show({
                            title: 'Entered Record Cannot be edited',
                            msg: 'Please clear the entered checkbox before editing this record',
                            buttons: Ext.MessageBox.OK
                        });

                        return false;
                    }
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
        header: 'ID',
        dataIndex: 'id',
        width: 50,
        disabled: true
    },{
        header: 'Flag',
        dataIndex: 'flagged',
        itemId: 'flagged',
        xtype: 'checkcolumn',
        width: 50
    },{
        header: 'Total Due',
        dataIndex: 'target_total',
        editor: {
            xtype: 'numberfield',
            allowBlank: false,
            selectOnFocus: true
        },
        width: 100,
        renderer: Ext.util.Format.usMoney
    },{
        header: 'Start',
        dataIndex: 'period_start',
        editor: {
            xtype: 'datefield',
            allowBlank: false,
            format: 'Y-m-d',
            selectOnFocus: true
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
            format: 'Y-m-d',
            selectOnFocus: true
        },
        width: 100,
        renderer: function(value) {
            return Ext.util.Format.date(value, 'Y-m-d');
        }
    },{
        header: 'Secondary Utility Account Number',
        dataIndex: 'supply_choice_id',
        editor: {
            xtype: 'textfield',
            selectOnFocus: true
        },
        minWidth: 200,
        flex: 1
    },{
        header: 'Usage',
        dataIndex: 'total_energy',
        editor: {
            xtype: 'numberfield',
            allowBlank: false,
            selectOnFocus: true
        },
        width: 100
    },{
        header: 'Total Charges',
        dataIndex: 'supply_total',
        width: 100,
        renderer: Ext.util.Format.usMoney
    },{
        header: 'Utility',
        dataIndex: 'utility_id',
        editor: {
            xtype: 'combo',
            store: 'Utilities',
            itemId: 'utility_combo',
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
            return record.get('utility');
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
            return record.get('supplier');
        }
    },{
        header: 'Supply Group',
        dataIndex: 'supply_group_id',
        emptyText: 'Unknown Supply Group',
        editor: {
            xtype: 'combo',
            store: 'SupplyGroups',
            itemId: 'supply_group_combo',
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
        renderer: function(val, metaDate, record){
            return record.get('supply_group');
        },
        minWidth: 250,
        flex: 1
    },{
        header: 'Service',
        dataIndex: 'service',
        editor: {
            xtype: 'combo',
            name: 'service',
            itemId: 'service_combo',
            store: 'Services',
            triggerAction: 'all',
            valueField: 'name',
            displayField: 'value',
            queryMode: 'local',
            forceSelection: false,
            selectOnFocus: true
        },
        width: 100
    },{
        header: 'Next Meter Read',
        dataIndex: 'next_meter_read_date',
        editor: {
            xtype: 'datefield',
            allowBlank: false,
            format: 'Y-m-d',
            selectOnFocus: true
        },
        width: 100,
        renderer: function(value) {
            return Ext.util.Format.date(value, 'Y-m-d');
        }
    },{
        header: 'Meter Number',
        dataIndex: 'meter_identifier',
        editor: {
            xtype: 'textfield',
            selectOnFocus: true
        },
        width: 100,
        hidden: true
    },{
        header: 'Due Date',
        dataIndex: 'due_date',
        width: 100,
        renderer: function(value) {
            return Ext.util.Format.date(value, 'Y-m-d');
        },
        hidden:true
    },{
        xtype: 'checkcolumn',
        text: 'Time Of Use',
        itemId: 'tou',
        dataIndex: 'tou'
    },{
        xtype: 'checkcolumn',
        text: 'Bill Entered',
        dataIndex: 'entered'
    }],

    dockedItems: [{
        dock: 'top',
        xtype: 'toolbar',
        layout: {
            overflowHandler: 'Menu'
        },
        items: [{
                xtype: 'label',
                text: '',
                padding: 5,
                id: 'utilbillAccountLabel'
            },{
                xtype: 'button',
                action: 'utilbillPrevious',
                text: 'Previous',
                disabled: true
            },{
                xtype: 'button',
                action: 'utilbillNext',
                text: 'Next',
                disabled: false
            },{
                xtype: 'button',
                action: 'utilbillHelp',
                text: 'Show Utility Bill Help',
                icon: 'icons/icon-question.png',
                disabled: false
            }
        ]
    }]
});
