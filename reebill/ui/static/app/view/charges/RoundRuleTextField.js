Ext.define('ReeBill.view.RoundRuleTextField', {
    extend: 'Ext.form.field.Text',
    alias: 'widget.roundRuleTextField',

    fieldLabel: 'Round Rule:',
    labelWidth: 80,
    width: 230,

    lastRecord: null,
    lastDataIndex: null
});