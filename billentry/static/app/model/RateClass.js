Ext.define('BillEntry.model.RateClass', {
    extend: 'Ext.data.Model',
    fields: [
        {name: 'name', type: 'string'},
        {name: 'id', type: 'int'},
        {name: 'utility_id', type: 'int'}
    ]
});
