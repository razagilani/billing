Ext.define('ReeBill.view.preferences.CurrencySpinner', {
    extend: 'Ext.form.field.Spinner',
    alias: 'widget.currencyspinner',

    onSpinUp: function() {
        var me = this;
        if (!me.readOnly) {
           me.setValue(me.getValue() + me.step);
        }
    },

    onSpinDown: function() {
        var me = this;
        if (!me.readOnly) {
           me.setValue(me.getValue() - me.step);
        }
    },

    valueToRaw: function(obj){
        return Ext.util.Format.usMoney(obj)
    },

    rawToValue: function(obj){
        var numberOffset = obj[0] === '-' ? 2 : 1;
        var multiplier = obj[0] === '-' ? -1 : 1;
        return parseFloat(obj.substring(numberOffset)) * multiplier;
    }
});
