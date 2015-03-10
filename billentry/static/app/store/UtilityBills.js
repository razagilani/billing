Ext.define('ReeBill.store.UtilityBills', {
    extend: 'Ext.data.Store',
    requires: ['ReeBill.model.UtilityBill'],
    model: 'ReeBill.model.UtilityBill',

    autoLoad: false,
    autoSync: true,

	proxy: {
		type: 'rest',

        simpleSortMode: true,
        pageParam: false,
        startParam: false,
        sortParam: false,
        limitParam: false,

        url: 'http://'+window.location.host+'/utilitybills/utilitybills',
		reader: {
			type: 'json',
			root: 'rows',
			totalProperty: 'results'
		},

        writer: {
            writeAllFields: false
        },

        listeners:{
            exception: utils.makeProxyExceptionHandler('UtilityBills'),
            scope: this
        }
	},

    getLastEndDate: function(){
        if(this.count() === 0){
            return false;
        }

        var lastDate = new Date(0);
        this.each(function(record){
            var pEnd = record.get('period_end');
            if(pEnd > lastDate){
                lastDate = pEnd;
            }
        }, this);
        return lastDate;
    },


    sorters: [{
        property: 'due_date',
        direction: 'DESC'
    }]
});
