Ext.define('ReeBill.view.JournalEntries', {
    extend: 'Ext.grid.Panel',

    title: 'Journal Entries',
    alias: 'widget.journalEntries',    
    store: 'JournalEntries',
    
    viewConfig: {
        trackOver: false,
        stripeRows: true,
        getRowClass: function(record) {

        }
    },
    
    columns: [{
        xtype: 'datecolumn', 
        dataIndex: 'date',
        header: 'Date',
        width: 150,
        format: 'Y-m-d H:i:s'
    },{
        header: 'User',
        sortable: true,
        dataIndex: 'user'
    },{
        header: 'Account',
        sortable: true,
        dataIndex: 'account'
    },{
        header: 'Sequence',
        sortable: true,
        dataIndex: 'sequence'
    },{
        header: 'Event',
        sortable: true,
        dataIndex: 'event',
        width: 600
    }]
});