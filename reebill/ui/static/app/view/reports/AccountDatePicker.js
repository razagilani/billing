Ext.define('ReeBill.view.reports.AccountDatePicker', {
    extend: 'Ext.window.Window',
    requires: ['ReeBill.store.Accounts'],
    title: 'Select Account and Date Range',
    alias: 'widget.accountDatePicker',
    height: 200,
    width: 400,
    layout: 'fit',
    modal: true,
    hidden: true,
    hideMode: 'visibility',
    closeAction: 'hide',

    items: [{
        xtype: 'form',
        bodyPadding: 5,
        standardSubmit: true,
        items:[{
            xtype: 'fieldset',
            title: 'Export Settings',
            defaults: {
                anchor: '100%',
                labelWidth: 150
            },
            collapsible: false,
            items: [{
                xtype: 'combo',
                name: 'account',
                store: 'Accounts',
                fieldLabel: 'Account',
                valueField: 'account',
                queryMode: 'local',
                typeAhead: true,
                triggerAction: 'all',
                emptyText:'All Accounts',
                selectOnFocus:true,
                allowBlank: true,
                tpl: Ext.create(
                    'Ext.XTemplate',
                    '<tpl for=".">',
                    '<div class="x-boundlist-item" >',
                    '{account}',
                    '</div>',
                    '</tpl>'
                ),
                displayTpl: Ext.create(
                    'Ext.XTemplate',
                    '<tpl for=".">',
                    '{account}',
                    '</tpl>'
                ),
                        },{
                xtype: 'datefield',
                fieldLabel: 'From',
                name: 'period_start',
                emptyText: 'All Time',
                allowBlank: true,
            },{
                xtype: 'datefield',
                fieldLabel: 'To',
                name: 'period_end',
                emptyText: 'All Time',
                allowBlank: true,
            }]
        }],

        buttons: [{
            xtype: 'button',
            text: 'Reset',
            action: 'resetAccountDatePicker'
        },{
            xtype: 'button',
            text: 'Save',
            iconCls: 'silk-disk',
            action: 'submitAccountDatePicker'
        }]
    }]
});
