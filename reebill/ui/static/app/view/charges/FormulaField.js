Ext.define('ReeBill.view.FormulaField', {
    extend: 'Ext.form.field.Text',
    alias: 'widget.formulaField',

    fieldLabel: 'Formula:',
    labelWidth: 50,
    minWidth: 300,
    flex:1,

    lastRecord: null,
    lastDataIndex: null
});