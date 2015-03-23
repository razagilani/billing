Ext.define('BillEntry.view.utilitybills.UtilityBills', {
    extend: 'Ext.grid.Panel',
    alias: 'widget.utilityBills',
    store: 'UtilityBills',
    
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
        header: 'Total',
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
        minWidth: 125,
        flex: 1
    },{
        header: 'Energy',
        dataIndex: 'total_energy',
        editor: {
            xtype: 'numberfield',
            allowBlank: false,
            selectOnFocus: true
        },
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
            minChars: 1,
            selectOnFocus: true
        },
        width: 100
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
            minChars: 1,
            selectOnFocus: true
        },
        width: 200
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
        header: 'Due Date',
        dataIndex: 'due_date',
        width: 100,
        renderer: function(value) {
            return Ext.util.Format.date(value, 'Y-m-d');
        },
        hidden:true
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
