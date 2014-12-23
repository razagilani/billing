Ext.define('ReeBill.controller.Preferences', {
    extend: 'Ext.app.Controller',

    stores: [
        'Preferences'
    ],

    views: [
        'preferences.CurrencySpinner', 'preferences.Preferences'
    ],
    
    refs: [{
        ref: 'differenceThresholdSpinner',
        selector: 'currencyspinner[name=difference_threshold]'
    },{
        ref: 'preferencesPanel',
        selector: 'preferencesPanel'
    },{
        ref: 'resetPreferencesButton',
        selector: 'button[action=resetPreferences]'
    },{
        ref: 'submitPreferencesButton',
        selector: 'button[action=submitPreferences]'
    }],
    
    init: function() {
        this.application.on({
            scope: this
        });
        
        this.control({
            'button[action=resetPreferences]': {
                click: this.handleResetPreferences
            },
            'button[action=submitPreferences]': {
                click: this.handleSubmitPreferences
            }
        });

        this.getPreferencesStore().on({
            load: this.handleResetPreferences,
            scope: this
        });
    },

    /**
     * Handle the panel being reset.
     */
    handleResetPreferences: function() {
        var store = this.getPreferencesStore();
        var panel = this.getPreferencesPanel();
        var fields = panel.getForm().getFields();
        fields.each(function(field){
            var name = field.getName();
            var val = field.getValue();
            var prefRec = store.getOrCreate(name, val);
            field.setValue(prefRec.get('value'));
        });
    },

    /**
     * Handle the submit button clicked
     */
    handleSubmitPreferences: function() {
        var store = this.getPreferencesStore();
        var panel = this.getPreferencesPanel();
        var fields = panel.getForm().getFields();
        fields.each(function(field){
            var name = field.getName();
            var val = field.getValue();
            store.setOrCreate(name, val);
        });
    }
});
