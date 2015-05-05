Ext.define('ReeBill.model.SupplyGroup', {
    extend: 'Ext.data.Model',
    fields: [
        {name: 'name', type: 'string'},
        {name: 'id', type: 'int'},
        {name: 'supplier_id', type: 'int'}
    ],
    belongsTo: [{
            name: 'supplygroups',
            model: 'Supplier',
            associationKey: 'supplygroups'
        }]
});

