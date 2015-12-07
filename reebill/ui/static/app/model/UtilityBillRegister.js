Ext.define('ReeBill.model.UtilityBillRegister', {
    extend: 'Ext.data.Model',
    fields: [
        {name: 'active_periods', convert: function(value, record){
            if(typeof(value) === 'string'){
                return Ext.JSON.decode(value);
            }
            return value
        }, defaultValue: null},
        {name: 'meter_identifier', type: 'string'},
        {name: 'identifier', type: 'string'},
        {name: 'reg_type', type: 'string'},
        {name: 'register_binding', type: 'string'},
        {name: 'description', type: 'string'},
        {name: 'quantity', type: 'float'},
        {name: 'unit', type: 'string'},
        {name: 'estimated', type: 'boolean'},
        {name: 'utilbill_id', type: 'int'}
    ]
});