Ext.define('ReeBill.store.Services', {
    extend: 'Ext.data.Store',

    fields: ['name', 'value'],
    data: [
        {name: 'Gas', value: 'Gas'},
        {name: 'Electric', value: 'Electric'}
    ]
});
