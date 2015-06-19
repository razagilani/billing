Ext.define('BillEntry.model.Charge', {
    extend: 'Ext.data.Model',
    fields: [
        {name: 'id', type: 'int'},
        {name: 'utilbill_id', type: 'int'},
        {name: 'rsi_binding', type: 'string'},
        {name: 'target_total', type: 'float'},
    ]
});
