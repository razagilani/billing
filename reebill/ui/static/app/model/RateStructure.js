Ext.define('ReeBill.model.RateStructure', {
    extend: 'Ext.data.Model',
    fields: [
        {name: 'id'},
        {name: 'rsi_binding'},
        {name: 'description'},
        {name: 'quantity'},
        {name: 'quantity_units'},
        {name: 'rate'},
        {name: 'shared'},
        {name: 'has_charge'},
        {name: 'round_rule'},
        {name: 'group'}
    ]
});