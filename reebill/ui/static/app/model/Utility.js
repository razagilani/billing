Ext.define('ReeBill.model.Utility', {
    extend: 'Ext.data.Model',
    fields: [
        {name: 'name', type: 'string'},
        {name: 'id', type: 'int', useNull: true},
        {name: 'address_id', type: 'int'},
        {name: 'guid', type: 'string'},
        {name: 'discriminator', type: 'string'},
        {name: 'supply_group_id', type: 'int'}
    ],
    hasMany: {
            model: 'RateClass',
            name: 'rateclasses',
            foreignKey: 'utility_id',
            accosiationKey: 'rateclasses'
        }
});
