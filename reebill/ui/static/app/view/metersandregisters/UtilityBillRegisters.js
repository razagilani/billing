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
        renderer: function(value){
            console.log()
            var selectedBill = ReeBill.getApplication().getController('UtilityBills')
                .getUtilityBillsGrid().getSelectionModel().getSelection()[0];
            return selectedBill.get('service');
        },
    },{
        header: 'Meter ID',
        dataIndex: 'meter_identifier',
        sortable: false,
        editor: {
            xtype: 'textfield',
        },
        width: 150,
    },{
        header: 'Register ID',
        dataIndex: 'identifier',
        sortable: false,
        editor: {
            xtype: 'textfield',
        },
        width: 150,
    },{
        header: 'Type',
        dataIndex: 'reg_type',
        sortable: false,
        editor: {
            xtype: 'textfield',
            allowBlank: false
        },
        width: 100,
    },{
        header: 'Register Binding',
        dataIndex: 'register_binding',
        sortable: false,
        editor: {
            xtype: 'textfield',
            allowBlank: false
        },
        width: 200,
    },{
        header: 'Quantity',
        dataIndex: 'quantity',
        sortable: false,
        editor: {
            xtype: 'textfield',
            allowBlank: false
        },
        width: 150,
    },{
        header: 'Units',
        dataIndex: 'quantity_units',
        width: 100,
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
        },
        flex: 1
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
