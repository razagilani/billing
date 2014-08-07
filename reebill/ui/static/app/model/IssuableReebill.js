Ext.define('ReeBill.model.IssuableReebill', {
    extend: 'Ext.data.Model',
    fields: [
        {name: 'id'},
        {name: 'account'},
        {name: 'sequence'},
        {name: 'mailto'},
        {name: 'util_total'},
        {name: 'reebill_total'},
        {name: 'matching'},
        {name: 'difference'}
    ]
});