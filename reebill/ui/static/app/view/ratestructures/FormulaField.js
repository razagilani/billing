Ext.define('ReeBill.view.FormulaField', {
    extend: 'Ext.form.field.Text',
    alias: 'widget.formulaField',

    fieldLabel: 'Formula:',
    labelWidth: 60,
    width: 600,

    lastRecord: null,
    lastDataIndex: null
});