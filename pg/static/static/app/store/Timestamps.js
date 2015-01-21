Ext.define('ReeBill.store.Timestamps', {
    extend: 'Ext.data.Store',

    fields: ['name', 'value'],
    data: [
        {name: '%Y-%m-%d %H:%M:%S', value: '%Y-%m-%d %H:%M:%S'},
        {name: '%Y/%m/%d %H:%M:%S', value: '%Y/%m/%d %H:%M:%S'},
        {name: '%m/%d/%Y %H:%M:%S', value: '%m/%d/%Y %H:%M:%S'},
        {name: '%Y-%m-%dT%H:%M:%SZ', value: '%Y-%m-%dT%H:%M:%SZ'}
    ]

});
