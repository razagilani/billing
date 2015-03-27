Ext.define('BillEntry.store.ServiceTypes', {
    extend: 'Ext.data.Store',
    fields: ['display_name', 'service_type'],
    data: [
        {display_name: 'Thermal', service_type: 'thermal'},
        {display_name: 'PV', service_type: 'pv'},
        {display_name: 'None', service_type: null}
    ]
});
