Ext.define('ReeBill.model.Reebill', {
    extend: 'Ext.data.Model',
    fields: [
        {name: 'action'}, // Allows for other actions besides CRUD (e.g. 'render')
        {name: 'action_value'}, // Additional data associated with the action
        // Model data
        {name: 'account'},
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
        {name: 'ree_charge'},
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
        {name: 'billing_address_id'},
        {name: 'service_address'},
        {name: 'service_address_id'},
        {name: 'processed'},
        // Data for Issuable Reebills
        {name: 'mailto'},
        {name: 'readings'},
        {name: 'groups'},
        {name: 'utilbill_total'},
        {name: 'adjustment', convert: function(value, record){
            return record.get('manual_adjustment') + record.get('total_adjustment')
        }},
        {name: 'difference', convert: function(value, record){
            return Math.abs(record.get('actual_total') - record.get('utilbill_total'))
        }},
        {name: 'group', type: 'string', convert: function(value, record){
            if(record.get('processed') === true){
                return 'Processed Reebills'
            }

            var store = Ext.getStore('Preferences')
            var threshold = Math.abs(store.getAt(
                store.find('key', 'difference_threshold')).get('value'))

            var diff = record.get('difference')
            return diff < threshold ? 'Reebills with matching Totals' : 'Reebills without matching Totals'
        }},
    ]
});
