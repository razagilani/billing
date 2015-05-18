Ext.define('BillEntry.model.UtilityBill', {
    extend: 'Ext.data.Model',
    fields: [
        {name: 'action', type: 'string'}, // Allows for other actions besides CRUD (e.g. 'render')
        {name: 'action_value'}, // Additional data associated with the action
        // Model data
        {name: 'id'},
        {name: 'name'},
        {name: 'utility_account_id', type: 'int'},
        {name: 'rate_class', type:'string', mapping: function( data )
            { if (data.rate_class==null)
                    return 'Unknown Rate Class';
              else
                    return data.rate_class;  }},
        {name: 'utility'},
        {name: 'supplier', type:'string', mapping: function( data ) {
            if (data.supplier==null)
                return 'Unknown Supplier' ;
            else
                return data.supplier;}},
        {name: 'supply_group', 'type': 'string', mapping: function( data ) {
            if (data.supply_group==null)
                    return 'Unknown Supply Group';
             else
                    return data.supply_group;  }
        },
        {name: 'supply_group_id', type: 'int'},
        {name: 'period_start', type: 'date', dateFormat: 'Y-m-d' },
        {name: 'period_end', type: 'date', dateFormat: 'Y-m-d' },
        {name: 'total_energy', type: 'float'},
        {name: 'total_charges', type: 'float' },
        {name: 'target_total', type: 'float' },
        {name: 'service', type:'string'},
        {name: 'processed'},
        {name: 'editable'},
        {name: 'sha256_hexdigest'},
        {name: 'pdf_url'},

        // new
        {name: 'service_address'},
        {name: 'computed_total', type: 'float'},
        {name: 'next_meter_read_date', type: 'date', dateFormat: 'Y-m-d' },
        {name: 'supply_total'},
        {name: 'utility_account_number'},
        {name: 'supply_choice_id'},
        {name: 'due_date', type: 'date', dateFormat: 'Y-m-d'},
        {name: 'wiki_url'},
        {name: 'entered'},
        {name: 'meter_identifier'},
        {name: 'flagged'},
        {name: 'tou'}
    ]
});
