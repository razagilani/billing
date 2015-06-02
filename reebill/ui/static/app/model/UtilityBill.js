Ext.define('ReeBill.model.UtilityBill', {
    extend: 'Ext.data.Model',
    fields: [
        {name: 'action', type: 'string'}, // Allows for other actions besides CRUD (e.g. 'render')
        {name: 'action_value'}, // Additional data associated with the action
        // Model data
        {name: 'id'},
        {name: 'name'},
        {name: 'account'},
        {name: 'rate_class', type:'string'},
        {name: 'rate_class_id', type: 'int', useNull:true},
        {name: 'utility', type:'string'},
        {name: 'utility_id', type: 'int', useNull:true},
        {name: 'supplier', type:'string'},
        {name: 'supplier_id', type: 'int', useNull:true},
        {name: 'supply_group'},
        {name: 'supply_group_id', type: 'int', useNull:true},
        {name: 'period_start', type: 'date', dateFormat: 'Y-m-d' },
        {name: 'period_end', type: 'date', dateFormat: 'Y-m-d' },
        {name: 'total_charges', type: 'float' },
        {name: 'target_total', type: 'float' },
        {name: 'computed_total', type: 'float'},
        {name: 'reebills'},
        {name: 'state', type: 'string'},
        {name: 'service', type: 'string'},
        {name: 'processed'},
        {name: 'editable'},
        {name: 'sha256_hexdigest'},
        {name: 'pdf_url'}
    ]
});
