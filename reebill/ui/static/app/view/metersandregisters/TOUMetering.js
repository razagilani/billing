Ext.define('ReeBill.view.metersandregisters.TOUMetering', {
    extend: 'Ext.form.Panel',
    requires: ['Ext.slider.DynamicMultiSlider'],
    title: 'Time of Use Metering',

    alias: 'widget.TOUMetering',

    bodyPadding: 15,
    collapsible:false,
    floatable: false,

    items: [{
        xtype: 'label',
        text: 'For Time of Use metering the registers REG_PEAK and REG_OFFPEAK are required. A third register REG_INTERMEDIATE is optional.',
        margin: '0 0 5 0',
        style: {display: 'block'}
    },{
        xtype: 'label',
        text: 'The active periods have not been set for one or more register. Use the sliders to enter the active periods and press save below.',
        margin: '0 0 5 0',
        style: {display: 'block', color: 'red'},
        hidden: true,
        id: 'TOUMeteringWarningLabel'
    },{
        xtype: 'fieldset',
        title: 'Active Periods',
        defaults: {
            anchor: '100%',
            labelWidth: 200
        },
        collapsible: false,
        items: [{
            xtype: 'dynamicmultislider',
            width: 200,
            increment: 1,
            minValue: 0,
            maxValue: 23,
            fieldLabel: 'Weekdays',
            id: 'TOUMeteringSliderWeekdays'
        },{
            xtype: 'dynamicmultislider',
            width: 200,
            increment: 1,
            minValue: 0,
            maxValue: 23,
            fieldLabel: 'Weekends',
            id: 'TOUMeteringSliderWeekends'
        }]
    }],

    dockedItems: [{
        dock: 'bottom',
        xtype: 'toolbar',
        items: ['->',{
            xtype: 'button',
            text: 'Reset',
            action: 'resetTOUMetering'
        },{
            xtype: 'button',
            text: 'Save',
            action: 'saveTOUMetering'
        }]
    }]
});
