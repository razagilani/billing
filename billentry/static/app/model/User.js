Ext.define('BillEntry.model.User', {
    extend: 'Ext.data.Model',
    fields: [
        {name: 'id', type: 'int'},
        {name: 'email', type: 'string'},
        {name: 'count', type: 'int'}
    ]
});
