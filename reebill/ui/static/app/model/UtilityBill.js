Ext.define('ReeBill.model.UtilityBill', {
    extend: 'Ext.data.Model',
    fields: [
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
        {name: 'editable'}
    ]
});