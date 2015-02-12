Ext.define('ReeBill.view.utilitybills.UtilityBills', {
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
        header: 'Utility Account Number',
        dataIndex: 'utility_account_number',
        width: 125
    },{
        header: 'Secondary Utility Account Number',
        dataIndex: 'supply_choice_id',
        editor: {
            xtype: 'textfield'
        },
        width: 125
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
        width: 100
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
        header: 'Total Supply',
        dataIndex: 'supply_total',
        renderer: Ext.util.Format.usMoney,
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
            minChars: 1
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
        dataIndex: 'next_estimated_meter_read_date'
    }, {
        header: 'Service Address',
        dataIndex: 'service_address',
        minWidth: 500,
        flex: 1
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
            }
        ]
    }]
});
