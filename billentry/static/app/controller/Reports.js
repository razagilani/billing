Ext.define('BillEntry.controller.Reports', {
    extend: 'Ext.app.Controller',

    stores: [
        'Users', 'UtilityBills'
    ],

    views:[
        'reports.BillDetails',
        'reports.UserStatistics'
    ],

    refs: [{
        ref: 'startDateField',
        selector: 'datefield[name=start]'
    },{
        ref: 'endDateField',
        selector: 'datefield[name=end]'
    }],

    init: function() {
        this.application.on({
            scope: this
        });

        this.control({
            'datefield[name=end]': {
                change: this.handleDateRangeChange
            },
            'datefield[name=start]': {
                change: this.handleDateRangeChange
            },
            'panel[name=reportsTab]': {
                activate: this.handleActivate
            }
        });

    },

    /**
     * Handle the utility bill panel being activated.
     */
    handleActivate: function(){
        var startField = this.getStartDateField();
        var endField = this.getEndDateField();
        if(!startField.getValue() && !endField.getValue()) {
            var today = new Date();
            endField.setValue(today);
            startField.setValue(Ext.Date.add(today, Ext.Date.DAY, -7))
        }
    },

    /**
     * Handle the selected date range changing
     */
    handleDateRangeChange: function() {
        var start = this.getStartDateField().getValue();
        var end = this.getEndDateField().getValue();
        console.log('daterange change');
        if (start && end){
            var store = this.getUsersStore();
            console.log(store, start, end, typeof start, typeof end);
            store.getProxy().setExtraParam('start', start.toISOString());
            store.getProxy().setExtraParam('end', end.toISOString());
            store.reload()
        }
    },

});
