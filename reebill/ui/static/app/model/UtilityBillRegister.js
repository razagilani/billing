Ext.define('ReeBill.model.UtilityBillRegister', {
    extend: 'Ext.data.Model',
    fields: [
        {name: 'service',
            convert: function(val) {
                if (val == 'gas') return 'Gas';
                if (val == 'electric') return 'Electric';
                return val;
            } 
        },
        {name: 'meter_identifier'},
        {name: 'identifier'},
        {name: 'reg_type'},
        {name: 'register_binding'},
        {name: 'description'},
        {name: 'quantity', type: 'float'},
        {name: 'quantity_units'}
    ]
});