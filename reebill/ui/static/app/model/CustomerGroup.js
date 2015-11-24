Ext.define('ReeBill.model.CustomerGroup', {
    extend: 'Ext.data.Model',
    fields: [
        {name: 'name', type: 'string'},
        {name: 'id', type: 'int'},
        {name: 'bill_email_recipient', type: 'int'}
    ]
});
