Ext.define('ReeBill.model.SupplyGroup', {
    extend: 'Ext.data.Model',
    fields: [
        {name: 'name', type: 'string'},
        {name: 'id', type: 'int', useNull: true},
        {name: 'supplier_id', type: 'int'},
        {name: 'service', type: 'string'}
    ]
});

