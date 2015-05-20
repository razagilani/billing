Ext.define('ReeBill.model.Reconciliation', {
    extend: 'Ext.data.Model',
    fields: [
        {name: 'customer_id'},
        {name: 'sequence'},
        {name: 'energy', type: 'float'},
        {name: 'current_energy', type: 'float'},
    ]
});
