Ext.define('ReeBill.model.Charge', {
    extend: 'Ext.data.Model',
    fields: [
        {name: 'type', type: 'string'},
        {name: 'rsi_binding', type: 'string'},
        {name: 'description', type: 'string'},
        {name: 'quantity', type: 'float'},
        {name: 'unit', type: 'string'},
        {name: 'rate', type: 'float'},
        {name: 'total', type: 'float'},
        {name: 'error', type: 'string', useNull: true},
        {name: 'has_charge', type: 'boolean'},
        {name: 'quantity_formula', type: 'string'},
        {name: 'roundrule', type: 'string'},
        {name: 'shared', type: 'boolean'},
        {name: 'utilbill_id', type: 'int'}
    ]
});