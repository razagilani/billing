Ext.define('BillEntry.store.Units', {
    extend: 'Ext.data.Store',

    fields: ['name', 'value'],
    data: [
        {name : 'dollars', value: 'dollars'},
        {name : 'kWh', value: 'kwh'},
        {name : 'BTU', value: 'BTU'},
        {name : 'MMBTU', value: 'MMBTU'},
        {name : 'therms', value: 'therms'},
        {name : 'kWD', value: 'kWD'},
    ]
});