Ext.define('ReeBill.view.journal.JournalEntries', {
    extend: 'Ext.grid.Panel',

    title: 'Journal Entries',
    alias: 'widget.journalEntries',    
    store: 'JournalEntries',
    
    viewConfig: {
        trackOver: false,
        stripeRows: true,
        getRowClass: function(record) {

        },
        enableTextSelection: true
    },
    
    columns: [{
        xtype: 'datecolumn', 
        dataIndex: 'date',
        header: 'Date',
        width: 170,
        flex: 0,
        format: 'Y-m-d H:i:s'
    },{
        header: 'User',
        sortable: true,
        dataIndex: 'user',
        width: 100,
        flex: 0
    },{
        header: 'Account',
        sortable: true,
        dataIndex: 'account',
        width: 80,
        flex: 0
    },{
        header: 'Sequence',
        sortable: true,
        dataIndex: 'sequence',
        width: 90,
        flex: 0
    },{
        header: 'Event',
        sortable: true,
        dataIndex: 'event',
        flex: 1
    }]
});
