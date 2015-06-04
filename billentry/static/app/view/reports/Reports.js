Ext.define('BillEntry.view.reports.Reports', {
    extend: 'Ext.panel.Panel',
    alias: 'widget.reports',
    title: "Reports",
    name: 'reportsTab',


    layout: {
        type: 'accordion',
        titleCollapse: true,
        animate: false
    },

    requires: [
        'BillEntry.view.reports.UserUtilBillCount',
        'BillEntry.view.reports.BillDetails'
    ],

    items: [{
        xtype: 'panel',
        title: 'Entered Bills',
        layout: {
            type: 'vbox',
            align : 'stretch',
            pack  : 'start'
        },
        items:[{
            xtype: 'form',
            height: 60,
            title: 'Select a Date/Time Range',
            items: [{
                xtype: 'fieldcontainer',
                layout: 'hbox',
                fieldDefaults: {
                    labelWidth: 30,
                    allowBlank: false,
                    flex: 1,
                    margin: '2 5 5 5'
                },
                items: [{
                        xtype: 'datefield',
                        fieldLabel: 'From:',
                        name: 'start'
                    }, {
                        xtype: 'datefield',
                        fieldLabel: 'To:',
                        name: 'end'
                }]
            }]
        },{
            xtype: 'userUtilBillCount',
            id: 'userUtilBillCountGrid',
            flex: 1
        },{
            xtype: 'billDetails',
            store: 'UserUtilityBills',
            id: 'reportUtilityBillsGrid',
            flex: 1,
            disabled: true,
            omitColumns: ['entered']
        }]
    },{
        title: 'Flagged Bills',
        xtype: 'billDetails',
        store: 'AllFlaggedUtilityBills',
        id: 'flaggedUtilityBillsGrid',
        omitColumns: ['flagged'],
        layout: 'fit'
    }]

});