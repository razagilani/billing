Ext.define('ReeBill.model.Payment', {
    extend: 'Ext.data.Model',
    fields: [
        {name: 'id'},
        {name: 'date_applied'},
        {name: 'date_received'},
        {name: 'description'},
        {name: 'credit'},
        {name: 'editable', type: 'boolean'}
   ]
});