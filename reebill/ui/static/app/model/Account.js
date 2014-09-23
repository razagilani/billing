Ext.define('ReeBill.model.Account', {
    extend: 'Ext.data.Model',
    fields: [
        {name: 'account'},
        {name: 'fb_utility_name'},
        {name: 'fb_rate_class'},
        {name: 'fb_service_address'},
        {name: 'ba_addressee'},
        {name: 'ba_city'},
        {name: 'ba_postal_code'},
        {name: 'ba_state'},
        {name: 'ba_street'},
        {name: 'discount_rate'},
        {name: 'late_charge_rate'},
        {name: 'sa_addressee'},
        {name: 'sa_city'},
        {name: 'sa_postal_code'},
        {name: 'sa_state'},
        {name: 'sa_street'},
        {name: 'service_type'},
        {name: 'template_account'},
        {name: 'codename'},
        {name: 'casualname'},
        {name: 'primusname'},
        {name: 'lastutilityserviceaddress'},
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
        {name: 'lastevent'},
        {name: 'lastissuedate'},
        {name: 'provisionable'},
        {name: 'lastrateclass'},
        {name: 'name'}
    ]
});