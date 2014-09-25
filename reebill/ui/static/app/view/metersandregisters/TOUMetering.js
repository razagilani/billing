Ext.define('ReeBill.view.TOUMetering', {
    extend: 'Ext.form.Panel',

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
        xtype: 'fieldset',
        title: 'Active Periods',
        defaults: {
            anchor: '100%',
            labelWidth: 200
        },
        collapsible: false,
        items: [{
            xtype: 'multislider',
            width: 200,
            values: [5, 9, 17, 21],
            increment: 1,
            minValue: 0,
            maxValue: 23,
            fieldLabel: 'Weekdays',
            id: 'TOUMeteringSliderWeekdays'
        },{
            xtype: 'multislider',
            width: 200,
            values: [5, 9, 17, 21],
            increment: 1,
            minValue: 0,
            maxValue: 23,
            fieldLabel: 'Weekends',
            id: 'TOUMeteringSliderWeekends'
        },{
            xtype: 'multislider',
            width: 200,
            values: [5, 9, 17, 21],
            increment: 1,
            minValue: 0,
            maxValue: 23,
            fieldLabel: 'Hollidays',
            id: 'TOUMeteringSliderHollidays'
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