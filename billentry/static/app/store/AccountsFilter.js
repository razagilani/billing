Ext.define('ReeBill.store.AccountsFilter', {
    extend: 'Ext.data.Store',
    fields: ['label', 'filter', 'value'],
    data: [{
        label: 'No filter',
        filter: Ext.create('Ext.util.Filter', {
            filterFn: function(item) {return true;},
            root: 'data'}),
        value: 'none'
    },{
        label: 'Bills To Be Entered',
        filter: Ext.create('Ext.util.Filter', {
            filterFn: function (item) {
                return item.get('bills_to_be_entered') == true ;},
            root: 'data'}),
        value: 'enter_bills'
    },{
        label: 'Bills Previously Entered',
        filter: Ext.create('Ext.util.Filter', {
            filterFn: function(item){
                return item.get('bills_to_be_entered') == false;},
            root: 'data'}),
        value: 'entered_bills'
    }]
});
