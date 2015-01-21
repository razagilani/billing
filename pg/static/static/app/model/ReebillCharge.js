Ext.define('ReeBill.model.ReebillCharge', {
    extend: 'Ext.data.Model',
    fields: [
        {name: 'group'},
        {name: 'uuid'},
        {name: 'rsi_binding'},
        {name: 'description'},
        {name: 'actual_quantity'},
        {name: 'quantity'},
        {name: 'unit'},
        {name: 'rate'},
        {name: 'actual_total', type: 'float'},
        {name: 'total', type: 'float'},
        {name: 'processingnote'}
    ]
});
