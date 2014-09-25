Ext.define('ReeBill.model.Charge', {
    extend: 'Ext.data.Model',
    fields: [
        {name: 'group'},
        {name: 'id'},
        {name: 'rsi_binding'},
        {name: 'description'},
        {name: 'quantity'},
        {name: 'quantity_units'},
        {name: 'rate', type: 'float'},
        {name: 'total', type: 'float'},
        {name: 'error'},
        {name: 'has_charge'},
        {name: 'quantity_formula'},
        {name: 'roundrule'},
        {name: 'shared'},
        {name: 'utilbill_id'}
    ]
});