Ext.define('ReeBill.model.Account', {
    extend: 'Ext.data.Model',
    fields: [
        // Received from server when the accounts list is loaded
        {name: 'utility_account_id', type: 'int'},
        {name: 'account', type: 'string'},
        {name: 'tags', type: 'string'},
        {name: 'utility_account_number', type: 'string'},
        {name: 'utilityserviceaddress', type: 'string'},
        {name: 'fb_utility_name', type: 'string'},
        {name: 'fb_rate_class', type: 'string'},
        {name: 'lastevent', type: 'string'},
        {name: 'codename', type: 'string'},
        {name: 'casualname', type: 'string'},
        {name: 'primusname', type: 'string'},

        // Needed when a new account is created
        {name: 'name', type: 'string'},
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
        {name: 'payee'}

    ],
    idProperty: 'utility_account_id'
});
