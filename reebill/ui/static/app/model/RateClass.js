Ext.define('ReeBill.model.RateClass', {
    extend: 'Ext.data.Model',
    fields: [
        {name: 'name', type: 'string'},
        {name: 'id', type: 'int'},
        {name: 'utility_id', type: 'int'}
    ],
    belongsTo: [{
            name: 'rateclasses',
            model: 'Utility',
            associationKey: 'rateclasses'
        }]
});
