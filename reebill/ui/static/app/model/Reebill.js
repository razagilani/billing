Ext.define('ReeBill.model.Reebill', {
    extend: 'Ext.data.Model',
    fields: [
        {name: 'action'}, // Allows for other actions besides CRUD (e.g. 'render')
        {name: 'sequence'},
        {name: 'period_start'},
        {name: 'period_end'},
        {name: 'corrections'}, // human-readable (could replace with a nice renderer function for max_version)
        {name: 'issue_date'},
        {name: 'max_version'}, // machine-readable
        {name: 'hypothetical_total'},
        {name: 'actual_total'},
        {name: 'ree_quantity'},
        {name: 'ree_value'},
        {name: 'prior_balance'},
        {name: 'payment_received'},
        {name: 'total_adjustment'},
        {name: 'balance_forward'},
        {name: 'balance_forward'},
        {name: 'ree_charges'},
        {name: 'balance_due'},
        {name: 'total_error'},
        {name: 'issued'},
        {name: 'services'}
    ]
});