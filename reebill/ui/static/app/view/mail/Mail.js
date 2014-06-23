Ext.define('ReeBill.view.Mail', {
    extend: 'Ext.grid.Panel',

    title: 'Mail',
    alias: 'widget.mail',    
    store: 'Reebills',
    
    viewConfig: {
        trackOver: false,
        stripeRows: true,
        getRowClass: function(record) {

        }
    },

    columns: [{
        header: 'Sequence',
        sortable: true,
        dataIndex: 'sequence',
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
            text: 'Mail',
            iconCls: 'silk-email',
            action: 'email'
        }]
    }]
});