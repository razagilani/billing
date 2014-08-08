Ext.define('ReeBill.controller.Preferences', {
    extend: 'Ext.app.Controller',

    stores: [
        'Preferences'
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
                click: this.hanldeResetPreferences
            },
            'button[action=submitPreferences]': {
                click: this.handleSubmitPreferences
            }
        });

        this.getPreferencesStore().on({
            load: this.hanldeResetPreferences,
            scope: this
        });
    },

    /**
     * Handle the panel being reset.
     */
    hanldeResetPreferences: function() {
        var store = this.getPreferencesStore();
        var values = this.getPreferencesPanel();
        console.log(store, panel, panel.getForm().getValues())
    },

    /**
     * Handle the submit button clicked
     */
    handleSubmitPreferences: function() {

    }
});
