Ext.define('ReeBill.model.Charge', {
    extend: 'Ext.data.Model',
    fields: [
        {name: 'group'},
        {name: 'id'},
        {name: 'rsi_binding'},
        {name: 'description'},
        {name: 'quantity'},
        {name: 'quantity_units'},
        {name: 'rate'},
        {name: 'total', type: 'float'},
        {name: 'processingnote'},
        {name: 'error'},
        {name: 'has_charge'},
        {name: 'quantity_formula'},
        {name: 'rate_formula'},
        {name: 'roundrule'},
        {name: 'shared'},
        {name: 'utilbill_id'}
    ],

    formulaMappings: {
        'quantity': 'quantity_formula',
        'rate': 'rate_formula'
    },

    getFormulaKey: function(originalKey){
        if(this.formulaMappings[originalKey] !== undefined){
            return this.formulaMappings[originalKey];
        }
        return originalKey;
    }
});