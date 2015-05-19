Ext.define('BillEntry.model.Utility', {
    extend: 'Ext.data.Model',
    fields: [
        {name: 'name', type: 'string'},
        {name: 'id', type: 'int', useNull: true},
        {name: 'address_id', type: 'int'},
        {name: 'guid', type: 'string'},
        {name: 'discriminator', type: 'string'},
        {name: 'sos_supply_group_id', type: 'int'}
    ]
});
