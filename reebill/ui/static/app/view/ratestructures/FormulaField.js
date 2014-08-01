Ext.define('ReeBill.view.FormulaField', {
    extend: 'Ext.form.field.Text',
    alias: 'widget.formulaField',

    fieldLabel: 'Formula:',
    width: 600,

    lastRecord: null,
    lastDataIndex: null
});