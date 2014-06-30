Ext.define('ReeBill.view.UtilityBillRegisters', {
    extend: 'Ext.grid.Panel',

    title: 'Utility Bill Registers',
    alias: 'widget.utilityBillRegisters',    
    store: 'UtilityBillRegisters',
    preventHeader: true,

    plugins: [
        Ext.create('Ext.grid.plugin.CellEditing', {
            clicksToEdit: 2
        })
    ],

    viewConfig: {
        trackOver: false,
        stripeRows: true,
        getRowClass: function(record) {

        }
    },
    
    columns: [{
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
        header: 'Meter ID',
        dataIndex: 'meter_id',
        sortable: false,
        editor: {
            xtype: 'textfield',
            allowBlank: false
        },
        width: 100,
    },{
        header: 'Register ID',
        dataIndex: 'register_id',
        sortable: false,
        editor: {
            xtype: 'textfield',
            allowBlank: false
        },
        width: 100,
    },{
        header: 'Type',
        dataIndex: 'type',
        sortable: false,
        editor: {
            xtype: 'textfield',
            allowBlank: false
        },
        width: 70,
    },{
        header: 'RSI Binding',
        dataIndex: 'binding',
        sortable: false,
        editor: {
            xtype: 'textfield',
            allowBlank: false
        },
        width: 100,
    },{
        header: 'Quantity',
        dataIndex: 'quantity',
        sortable: false,
        editor: {
            xtype: 'textfield',
            allowBlank: false
        },
        width: 70,
    },{
        header: 'Units',
        dataIndex: 'quantity_units',
        width: 70,
        sortable: true,
        editor: {
            xtype: 'combo',
            name: 'service',
            store: 'Units',
            triggerAction: 'all',
            valueField: 'value',
            displayField: 'name',
            queryMode: 'local',
            forceSelection: true,
            selectOnFocus: true
        }  
    },{
        header: 'Description',
        dataIndex: 'description',
        sortable: false,
        editor: {
            xtype: 'textfield',
            allowBlank: false
        }
    }],

    dockedItems: [{
        dock: 'top',
        xtype: 'toolbar',
        items: [{
            xtype: 'button',
            text: 'New',
            action: 'newUtilityBillRegister',
            iconCls: 'silk-add'
        },{        
            xtype: 'button',
            text: 'Remove',
            action: 'removeUtilityBillRegister',
            iconCls: 'silk-delete',
            disabled: true
        }]
    }]
});