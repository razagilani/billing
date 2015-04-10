Ext.define('ReeBill.store.Types', {
    extend: 'Ext.data.Store',

    fields: ['name', 'value'],
    data: [
        {name : 'supply', value: 'supply'},
        {name : 'distribution', value: 'distribution'}
    ]
});
