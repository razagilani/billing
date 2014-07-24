Ext.define('ReeBill.model.Reebill', {
    extend: 'Ext.data.Model',
    fields: [
        {name: 'action'}, // Allows for other actions besides CRUD (e.g. 'render')
        {name: 'action_value'}, // Additional data associated with the action
        // Model data
        {name: 'customer_id'},
        {name: 'sequence'},
        {name: 'period_start'},
        {name: 'period_end'},
        {name: 'corrections'}, // human-readable (could replace with a nice renderer function for max_version)
        {name: 'issue_date'},
        {name: 'version'}, // machine-readable
        {name: 'hypothetical_total'},
        {name: 'actual_total'},
        {name: 'ree_quantity'},
        {name: 'ree_value'},
        {name: 'ree_charge'},
        {name: 'ree_savings'},
        {name: 'prior_balance'},
        {name: 'payment_received'},
        {name: 'total_adjustment'},
        {name: 'balance_forward'},
        {name: 'ree_charges'},
        {name: 'balance_due'},
        {name: 'total_error'},
        {name: 'issued'},
        {name: 'services'},
        {name: 'due_date'},
        {name: 'email_recipient'},
        {name: 'discount_rate'},
        {name: 'late_charge'},
        {name: 'late_charge_rate'},
        {name: 'manual_adjustment'},
        {name: 'billing_address'},
        {name: 'service_address'}
    ]
});
