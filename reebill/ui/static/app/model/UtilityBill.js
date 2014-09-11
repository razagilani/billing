Ext.define('ReeBill.model.UtilityBill', {
    extend: 'Ext.data.Model',
    fields: [
        {name: 'action'}, // Allows for other actions besides CRUD (e.g. 'render')
        {name: 'action_value'}, // Additional data associated with the action
        // Model data
        {name: 'id'},
        {name: 'name'},
        {name: 'account'},
        {name: 'rate_class'},
        {name: 'utility'},
        {name: 'period_start', type: 'date', dateFormat: 'Y-m-d' },
        {name: 'period_end', type: 'date', dateFormat: 'Y-m-d' },
        {name: 'total_charges', type: 'float' },
        {name: 'computed_total', type: 'float'},
        {name: 'reebills'},
        {name: 'state'},
        {name: 'service'},
        {name: 'processed'},
        {name: 'editable'},
        {name: 'sha256_hexdigest'},
        {name: 'pdf_url'}
    ]
});