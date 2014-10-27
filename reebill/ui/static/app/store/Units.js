Ext.define('ReeBill.store.Units', {
    extend: 'Ext.data.Store',

    fields: ['name', 'value'],
    data: [
        {name : 'dollars', value: 'dollars'},
        {name : 'kWh', value: 'kwh'},
        {name : 'ccf', value: 'ccf'},
        {name : 'BTU', value: 'btu'},
        {name : 'Therms', value: 'Therms'},
        {name : 'kWD', value: 'kWD'},
        {name : 'KQH', value: 'KQH'},
        {name : 'rkVA', value: 'rkVA'}
    ]
});