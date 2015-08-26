Ext.define('BillEntry.model.Supplier', {
    extend: 'Ext.data.Model',
    fields: [
        {name: 'name', type: 'string'},
        {name: 'id', type: 'int', useNull: true}
    ]
});
