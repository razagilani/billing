Ext.define('ReeBill.model.EstimatedRevenue', {
    extend: 'Ext.data.Model',
    fields: [
        {name: 'account'},
        {name: 'revenue_0_months_ago', mapping: 'revenue_0_months_ago.value'},
        {name: 'revenue_1_months_ago', mapping: 'revenue_1_months_ago.value'},
        {name: 'revenue_2_months_ago', mapping: 'revenue_2_months_ago.value'},
        {name: 'revenue_3_months_ago', mapping: 'revenue_3_months_ago.value'},
        {name: 'revenue_4_months_ago', mapping: 'revenue_4_months_ago.value'},
        {name: 'revenue_5_months_ago', mapping: 'revenue_5_months_ago.value'},
        {name: 'revenue_6_months_ago', mapping: 'revenue_6_months_ago.value'},
        {name: 'revenue_7_months_ago', mapping: 'revenue_7_months_ago.value'},
        {name: 'revenue_8_months_ago', mapping: 'revenue_8_months_ago.value'},
        {name: 'revenue_9_months_ago', mapping: 'revenue_9_months_ago.value'},
        {name: 'revenue_10_months_ago', mapping: 'revenue_10_months_ago.value'},
        {name: 'revenue_11_months_ago', mapping: 'revenue_11_months_ago.value'}
    ]
});
