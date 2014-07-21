Ext.define('ReeBill.view.UtilityBillVersions', {
    extend: 'Ext.form.field.ComboBox',

    alias: 'widget.utilityBillVersions',    

    queryMode: 'local',
    hideLabel: true,
    store: 'UtilityBillVersions',
    region: 'north',
    triggerAction: 'all',

    editable: false,

    value: '',

    valueField: 'version',

    tpl: '<tpl for="."><div class="x-boundlist-item"><tpl if="sequence">Reebill {sequence}-{version}: {issue_date}<tpl else>Current version</tpl></div></tpl>',
    displayTpl: Ext.create('Ext.XTemplate',
        '<tpl for=".">',
            '<tpl if="sequence">Reebill {sequence}-{version}: {issue_date}<tpl else>Current version</tpl>',
        '</tpl>'
    ),

    forceSelection: true,
    selectOnFocus: true
});