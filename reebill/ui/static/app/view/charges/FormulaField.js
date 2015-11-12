Ext.define('ReeBill.view.charges.FormulaField', {
    extend: 'Ext.form.field.Text',
    alias: 'widget.formulaField',

    fieldLabel: 'Formula:',
    labelWidth: 50,
    minWidth: 300,
    flex:1,

    lastRecord: null,
    lastDataIndex: null
});
