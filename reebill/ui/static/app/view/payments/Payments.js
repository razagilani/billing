Ext.define('ReeBill.view.Payments', {
    extend: 'Ext.grid.Panel',

    title: 'Payments',
    alias: 'widget.payments',    
    store: 'Payments',
    
    plugins: [
        Ext.create('Ext.grid.plugin.CellEditing', {
            clicksToEdit: 2
        })
    ],

    viewConfig: {
        trackOver: false,
        stripeRows: true,
        getRowClass: function(record) {
            if (!record.get('editable'))
                return 'payment-grid-frozen';
        }
    },
    
    columns: [{ 
        xtype: 'datecolumn', 
        dataIndex: 'date_received', 
        text: 'Date Received',
        width: 175,
        format: 'Y-m-d H:i:s'
    },{
        xtype: 'datecolumn', 
        dataIndex: 'date_applied', 
        text: 'Date Applied',   
        format: 'Y-m-d',
        editor: {
            xtype: 'datefield',
            allowBlank: false, 
            format: 'Y-m-d'
        },
        width: 125
    },{
        header: 'Description',
        sortable: true,
        dataIndex: 'description',
        editor: {
            xtype: 'textfield',
            allowBlank: false
        },
        width: 200
    },{
        header: 'Credit',
        sortable: true,
        dataIndex: 'credit',
        editor: {
            xtype: 'textfield',
            allowBlank: false
        },
        width: 125
    }],

    dockedItems: [{
        dock: 'top',
        xtype: 'toolbar',
        items: [{
            xtype: 'button',
            text: 'Insert',
            action: 'newPayment',
            iconCls: 'silk-add'
        },{        
            xtype: 'button',
            text: 'Remove',
            action: 'deletePayment',
            iconCls: 'silk-delete',
            disabled: true
        }]
    }]
});