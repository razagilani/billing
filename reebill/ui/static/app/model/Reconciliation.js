Ext.define('ReeBill.model.Reconciliation', {
    extend: 'Ext.data.Model',
    fields: [
        {name: 'customer_id'},
        {name: 'nextility_account_number'},
        {name: 'sequence'},
        {name: 'energy', type: 'float'},
        {name: 'current_energy', type: 'float'},
    ]
});
