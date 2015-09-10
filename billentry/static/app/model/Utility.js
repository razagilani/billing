Ext.define('BillEntry.model.Utility', {
    extend: 'Ext.data.Model',
    fields: [
        {name: 'name', type: 'string'},
        {name: 'id', type: 'int', useNull: true},
        {name: 'sos_supply_group_id', type: 'int'}
    ]
});
