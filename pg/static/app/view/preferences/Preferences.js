Ext.define('ReeBill.view.preferences.Preferences', {
    extend: 'Ext.form.Panel',

    title: 'Preferences',

    alias: 'widget.preferencesPanel',

    bodyPadding: 15,
    layout: 'fit',

    items: [{
        xtype: 'fieldset',
        title: 'User Preferences',
        name: 'preferencesfieldset',
        defaults: {
            anchor: '100%',
            labelWidth: 200
        },
        collapsible: false,
        items: [{
            xtype: 'currencyspinner',
            fieldLabel: 'Dollar Difference Threshold',
            name: 'difference_threshold',
            allowBlank: false,
            step: 0.01,
            value: 0.01
        },]
    }],

    buttons: [{
        xtype: 'button',
        text: 'Reset',
        action: 'resetPreferences'
    },{
        xtype: 'button',
        text: 'Submit',
        action: 'submitPreferences'
    }]
});
