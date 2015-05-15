Ext.define('ReeBill.model.UtilityBill', {
    extend: 'Ext.data.Model',
    fields: [
        {name: 'action', type: 'string'}, // Allows for other actions besides CRUD (e.g. 'render')
        {name: 'action_value'}, // Additional data associated with the action
        // Model data
        {name: 'id'},
        {name: 'name'},
        {name: 'account'},
        {name: 'rate_class', type:'string', mapping: function( data ) {
            if (data.rate_class==null)
                    return 'Unknown Rate Class';
            else
                    return data.rate_class;  }
        },
        {name: 'rate_class_id', type: 'int'},
        {name: 'utility'},
        {name: 'utility_id', type: 'int'},
        {name: 'supplier'},
        {name: 'supplier_id', type: 'int'},
        {name: 'supply_group', 'type': 'string', mapping: function( data ) {
            if (data.supply_group==null)
                    return 'Unknown Supply Group';
            else
                    return data.supply_group;  }
        },
        {name: 'supply_group_id', type: 'int'},
        {name: 'period_start', type: 'date', dateFormat: 'Y-m-d' },
        {name: 'period_end', type: 'date', dateFormat: 'Y-m-d' },
        {name: 'total_charges', type: 'float' },
        {name: 'target_total', type: 'float' },
        {name: 'computed_total', type: 'float'},
        {name: 'reebills'},
        {name: 'state', type:'string'},
        {name: 'service', type:'string'},
        {name: 'processed'},
        {name: 'editable'},
        {name: 'sha256_hexdigest'},
        {name: 'pdf_url'}
    ]
});
