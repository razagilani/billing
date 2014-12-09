Ext.define('ReeBill.view.accounts.AccountsCombo', {
    extend: 'Ext.form.field.ComboBox',
    requires: ['ReeBill.store.Accounts'],
    alias: 'widget.accountsCombo',
    
    store: 'Accounts',

    fieldLabel: 'Based on',
    tpl: Ext.create(
        'Ext.XTemplate',
        '<tpl for=".">',
        '<div class="x-boundlist-item" >',

        '{account} - ',
        '<tpl if=\'values.codename || values.casualname || values.primusname\'>',
        '<tpl if=\'values.codename\'>{codename}</tpl>',
        '<tpl if=\'values.codename && values.casualname\'>/</tpl>',
        '<tpl if=\'values.casualname\'>{casualname}</tpl>',
        '<tpl if=\'values.casualname && values.primusname\'>/</tpl>',
        '<tpl if=\'values.primusname\'>{primusname}</tpl>',
        ' - ',
        '</tpl>',
        '{fb_utility_name}:{fb_rate_class}',

        '</div>',
        '</tpl>'
    ),
    displayTpl: Ext.create(
        'Ext.XTemplate',
        '<tpl for=".">',

        '{account} - ',
        '<tpl if=\'values.codename || values.casualname || values.primusname\'>',
        '<tpl if=\'values.codename\'>{codename}</tpl>',
        '<tpl if=\'values.codename && values.casualname\'>/</tpl>',
        '<tpl if=\'values.casualname\'>{casualname}</tpl>',
        '<tpl if=\'values.casualname && values.primusname\'>/</tpl>',
        '<tpl if=\'values.primusname\'>{primusname}</tpl>',
        ' - ',
        '</tpl>',
        '{fb_utility_name}:{fb_rate_class}',

        '</tpl>'
    ),

    valueField: 'account',
    queryMode: 'local',
    typeAhead: true,
    triggerAction: 'all',
    emptyText:'Select...',
    selectOnFocus:true,
    allowBlank: false
});
