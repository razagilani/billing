Ext.define('ReeBill.model.MergeModel', {
    extend: 'Ext.data.Model',
    alias: 'model.mergemodel',

    fields: [{
        name: 'display',
        type: 'string',
        defaultValue: null,
        useNull: true
    },{
        name: 'val',
        type: 'string',
        defaultValue: null,
        useNull: true
    }]
});

