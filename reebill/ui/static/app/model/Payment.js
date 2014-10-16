Ext.define('ReeBill.model.Payment', {
    extend: 'Ext.data.Model',
    fields: [
        {name: 'id'},
        {
            name: 'date_applied',
            type: 'date',
            sortType: Ext.data.SortTypes.asDate
        },
        {
            name: 'date_received',
            type: 'date',
            sortType: Ext.data.SortTypes.asDate
        },
        {name: 'description'},
        {name: 'credit'},
        {name: 'editable', type: 'boolean'}
   ]
});