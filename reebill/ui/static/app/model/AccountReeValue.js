Ext.define('ReeBill.model.AccountReeValue', {
    extend: 'Ext.data.Model',
    fields: [
        {name: 'account'},
        {name: 'olap_id'},
        {name: 'casual_name'},
        {name: 'primus_name'},
        {name: 'ree_charges'},
        {name: 'actual_charges'},
        {name: 'hypothetical_charges'},
        {name: 'total_energy'},
        {name: 'average_ree_rate'},
        {name: 'outstandingbalance', type: 'float'},
        {name: 'days_late'}
    ]
});