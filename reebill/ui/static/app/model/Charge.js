Ext.define('ReeBill.model.Charge', {
    extend: 'Ext.data.Model',
    fields: [
        {name: 'group'},
        {name: 'id'},
        {name: 'rsi_binding'},
        {name: 'description'},
        {name: 'quantity'},
        {name: 'quantity_units'},
        {name: 'rate'},
        {name: 'total', type: 'float'},
        {name: 'processingnote'}
    ]
});