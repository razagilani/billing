Ext.define('ReeBill.store.RegisterBindings', {
    extend: 'Ext.data.Store',

    fields: ['name', 'value'],
    data: [
        {name : 'REG_TOTAL', value: 'REG_TOTAL'},
        {name : 'REG_DEMAND', value: 'REG_DEMAND'},
        {name : 'REG_PEAK', value: 'REG_PEAK'},
        {name : 'REG_INTERMEDIATE', value: 'REG_INTERMEDIATE'},
        {name : 'REG_OFFPEAK', value: 'REG_OFFPEAK'},
        {name : 'REG_TOTAL_SECONDARY', value: 'REG_TOTAL_SECONDARY'},
        {name : 'REG_TOTAL_TERTIARY', value: 'REG_TOTAL_TERTIARY'},
        {name : 'REG_POWERFACTOR', value: 'REG_POWERFACTOR'},
        {name : 'REG_PEAK_RATE_INCREASE', value: 'REG_PEAK_RATE_INCREASE'},
        {name : 'REG_INTERMEDIATE_RATE_INCREASE', value: 'REG_INTERMEDIATE_RATE_INCREASE'},
        {name : 'REG_OFFPEAK_RATE_INCREASE', value: 'REG_OFFPEAK_RATE_INCREASE'},
        {name : 'FIRST_MONTH_THERMS', value: 'FIRST_MONTH_THERMS'},
        {name : 'SECOND_MONTH_THERMS', value: 'SECOND_MONTH_THERMS'},
        {name : 'BEGIN_INVENTORY', value: 'BEGIN_INVENTORY'},
        {name : 'END_INVENTORY', value: 'END_INVENTORY'},
        {name : 'CONTRACT_VOLUME', value: 'CONTRACT_VOLUME'}
    ]
});