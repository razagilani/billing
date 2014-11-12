Ext.define('ReeBill.model.Reconciliation', {
    extend: 'Ext.data.Model',
    fields: [
        {name: 'account'},
        {name: 'sequence'},
        {name: 'bill_therms'},
        {name: 'olap_therms'},
        {name: 'oltp_therms'},
        {name: 'errors'}
    ]
});
