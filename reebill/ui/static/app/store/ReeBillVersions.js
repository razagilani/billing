Ext.define('ReeBill.store.ReeBillVersions', {
    extend: 'Ext.data.ArrayStore',

    fields: ['sequence', 'version', 'issue_date'],
    data: [{sequence: '', version: '', issue_date: ''}]
});
