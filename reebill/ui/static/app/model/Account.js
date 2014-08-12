Ext.define('ReeBill.model.Account', {
    extend: 'Ext.data.Model',
    fields: [
        {name: 'account'},
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
        {name: 'template_account'},
        {name: 'codename'},
        {name: 'casualname'},
        {name: 'primusname'},
        {name: 'utilityserviceaddress'},
        {name: 'lastperiodend', type:'date'},
        {name: 'lastevent'},
        {name: 'lastissuedate'},
        {name: 'provisionable'},
        {name: 'lastrateclass'},
        {name: 'name'}
    ]
});