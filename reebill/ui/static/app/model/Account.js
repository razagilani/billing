Ext.define('ReeBill.model.Account', {
    extend: 'Ext.data.Model',
    fields: [
        {name: 'account', type: 'string'},
        {name: 'fb_utility_name', type: 'string'},
        {name: 'fb_rate_class', type: 'string'},
        {name: 'fb_service_address', type: 'string'},
        {name: 'ba_addressee', type: 'string'},
        {name: 'ba_city', type: 'string'},
        {name: 'ba_postal_code', type: 'string'},
        {name: 'ba_state', type: 'string'},
        {name: 'ba_street', type: 'string'},
        {name: 'discount_rate', type: 'float'},
        {name: 'late_charge_rate', type: 'float'},
        {name: 'sa_addressee', type: 'string'},
        {name: 'sa_city', type: 'string'},
        {name: 'sa_postal_code', type: 'string'},
        {name: 'sa_state', type: 'string'},
        {name: 'sa_street', type: 'string'},
        {name: 'service_type', type: 'string'},
        {name: 'template_account'},
        {name: 'codename', type: 'string'},
        {name: 'casualname', type: 'string'},
        {name: 'primusname', type: 'string'},
        {name: 'lastutilityserviceaddress', type: 'string'},
        {name: 'lastperiodend', convert: function(value, record){
            // Calculate days since last processed util bill
            // If there has never been a utility bill (value == null)
            // it should be interpreted as infinite days since a utility bill
            // instead of zero
            if(value === null){
                return Infinity;
            }
            value = Ext.Date.parse(value, 'Y-m-d')
            var d = new Date();
            return Math.round((d-value)/(1000*60*60*24));
        }},
        {name: 'lastevent', type: 'string'},
        {name: 'lastissuedate'},
        {name: 'provisionable'},
        {name: 'lastrateclass', type: 'string'},
        {name: 'name', type: 'string'}
    ]
});