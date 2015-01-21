Ext.define('ReeBill.model.JournalEntry', {
    extend: 'Ext.data.Model',
    fields: [
        {name: '_id'},
        {name: 'date', type: 'date'},
        {name: 'user'},
        {name: 'account'},
        {name: 'sequence'},
        {name: 'event'},
        {name: 'msg'}
    ]
});
