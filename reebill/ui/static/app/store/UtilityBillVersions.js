Ext.define('ReeBill.store.UtilityBillVersions', {
    extend: 'Ext.data.ArrayStore',

    fields: ['sequence', 'version', 'issue_date'],
    data: [{sequence: '', version: '', issue_date: ''}]
});
