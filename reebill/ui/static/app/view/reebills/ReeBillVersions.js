Ext.define('ReeBill.view.reebills.ReeBillVersions', {
    extend: 'Ext.form.field.ComboBox',

    alias: 'widget.reeBillVersions',

    queryMode: 'local',
    hideLabel: true,
    store: 'ReeBillVersions',
    region: 'north',
    triggerAction: 'all',

    editable: false,

    value: '',

    valueField: 'version',

    tpl: '<tpl for="."><div class="x-boundlist-item">Reebill {sequence}-{version}<tpl if="issued">: {issue_date:date("Y-m-d")}</tpl></div></tpl>',
    displayTpl: Ext.create('Ext.XTemplate',
        '<tpl for=".">',
            'Reebill {sequence}-{version}<tpl if="issued">: {issue_date:date("Y-m-d")}</tpl>',
        '</tpl>'
    ),

    forceSelection: true
});
