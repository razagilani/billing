Ext.define('ReeBill.model.Account', {
    extend: 'Ext.data.Model',
    fields: [
        {name: 'id', type: 'int'},
        {name: 'account', type: 'string'},
        {name: 'utility_account_number', type: 'string'},
    ]
});
