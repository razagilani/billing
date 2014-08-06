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

//  Maps forumlas to their quantitites so they can be shown in the FormulaInput
//  Null means the FormulaInput should be disabled
    formulaMappings: {
        'quantity': 'quantity_formula',
        'rate': 'rate_formula',
        'shared': null,
        'has_charge': null,
    },

    getFormulaKey: function(originalKey){
        if(this.formulaMappings[originalKey] !== undefined){
            return this.formulaMappings[originalKey];
        }
        return originalKey;
    }
});