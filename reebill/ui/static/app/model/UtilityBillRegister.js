Ext.define('ReeBill.model.UtilityBillRegister', {
    extend: 'Ext.data.Model',
    fields: [
        {name: 'id'},
        {name: 'service', 
            convert: function(val) {
                if (val == 'gas') return 'Gas';
                if (val == 'electric') return 'Electric';
                return val;
            } 
        },
        {name: 'meter_id'},
        {name: 'register_id'},
        {name: 'type'},
        {name: 'binding'},
        {name: 'description'},
        {name: 'quantity'},
        {name: 'quantity_units'}
    ]
});