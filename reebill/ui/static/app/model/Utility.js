Ext.define('ReeBill.model.Utility', {
    extend: 'Ext.data.Model',
    fields: [
        {name: 'name', type: 'string'},
        {name: 'id', type: 'int', useNull: true},
        {name: 'address_id', type: 'int'},
        {name: 'guid', type: 'string'},
        {name: 'discriminator', type: 'string'},
        {name: 'sos_supplier_id', type: 'int'}
    ]
});
