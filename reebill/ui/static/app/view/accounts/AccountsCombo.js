Ext.define('ReeBill.view.AccountsCombo', {
    extend: 'Ext.form.field.ComboBox',
    alias: 'widget.accountsCombo',
    
    store: 'Accounts',

    fieldLabel: 'Based on',
    tpl: Ext.create(
        'Ext.XTemplate',
        '<tpl for=".">',
        '<div class="x-boundlist-item" >',
        '{account} - {codename} - {casualname} - {primusname} - {lastrateclass}',
        '</div>',
        '</tpl>'
    ),
    displayTpl: Ext.create(
        'Ext.XTemplate',
        '<tpl for=".">',
        '{account} - {codename} - {casualname} - {primusname} - {lastrateclass}',
        '</tpl>'
    ),

    valueField: 'account',
    mode: 'local',
    typeAhead: true,
    triggerAction: 'all',
    emptyText:'Select...',
    selectOnFocus:true,
    allowBlank: false
});