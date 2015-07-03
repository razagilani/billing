Ext.define('ReeBill.model.Payment', {
    extend: 'Ext.data.Model',
    fields: [
        {name: 'id'},
        {
            name: 'date_applied',
            type: 'date',
            dateReadFormat: 'Y-m-dTH:i:s',
            dateWriteFormat: 'Y-m-d H:i:s',
            sortType: Ext.data.SortTypes.asDate
        },
        {
            name: 'date_received',
            type: 'date',
            dateReadFormat: 'Y-m-dTH:i:s',
            dateWriteFormat: 'Y-m-d H:i:s',
            sortType: Ext.data.SortTypes.asDate
        },
        {name: 'description'},
        {name: 'credit'},
        {name: 'editable', type: 'boolean'}
   ]
});
