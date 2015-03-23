Ext.define('BillEntry.model.Account', {
    extend: 'Ext.data.Model',
    fields: [
        {name: 'id', type: 'int'},
        {name: 'account', type: 'string'},
        {name: 'utility_account_number', type: 'string'},
        {name: 'utility', type: 'string'},
        {name: 'service_address', type: 'string'},
        {name: 'bills_to_be_entered', type: 'boolean'},
    ]
});
