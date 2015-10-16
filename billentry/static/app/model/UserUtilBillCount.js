Ext.define('BillEntry.model.UserUtilBillCount', {
    extend: 'Ext.data.Model',
    fields: [
        {name: 'id', type: 'int'},
        {name: 'email', type: 'string'},
        {name: 'total_count', type: 'int'},
        {name: 'gas_count', type: 'int'},
        {name: 'electric_count', type: 'int'},
        {name: 'elapsed_time', type: 'int'}
    ]
});
