Ext.define('ReeBill.view.payments.Payments', {
    extend: 'Ext.grid.Panel',
    requires: ['Ext.datetimefield.DateTimeField'],
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
        format: 'Y-m-d H:i:s',
        editor: {
            xtype: 'datetimefield',
            allowBlank: false, 
            format: 'Y-m-d H:i:s'
        },
        width: 175
    },{
        header: 'Description',
        sortable: true,
        dataIndex: 'description',
        editor: {
            xtype: 'textfield',
            allowBlank: false
        },
        width: 300,
        flex: 1
    },{
        header: 'Credit',
        sortable: true,
        dataIndex: 'credit',
        editor: {
            xtype: 'numberfield',
            allowBlank: false
        },
        width: 125,
        renderer: Ext.util.Format.usMoney
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
    }],

    bbar: {
        xtype: 'pagingtoolbar',
        pageSize: 25,
        store: 'Payments',
        displayInfo: true,
        displayMsg: 'Displaying {0} - {1} of {2}'
    }
});
