Ext.define('BillEntry.controller.Reports', {
    extend: 'Ext.app.Controller',

    stores: [
        'UserUtilBillCounts',
        'UserUtilityBills',
        'AllFlaggedUtilityBills'
    ],

    views:[
        'reports.BillDetails',
        'reports.UserUtilBillCount',
        'reports.Reports'
    ],

    refs: [{
        ref: 'startDateField',
        selector: 'datefield[name=start]'
    },{
        ref: 'endDateField',
        selector: 'datefield[name=end]'
    },{
        ref: 'reportUtilityBillsGrid',
        selector: 'grid[id=reportUtilityBillsGrid]'
    },{
        ref: 'userUtilBillCountGrid',
        selector: 'grid[id=userUtilBillCountGrid]'
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
            },
            'panel[id=flaggedUtilityBillsGrid]': {
                expand: this.handleFlaggedBillsActivate
            },
            'grid[id=userUtilBillCountGrid]': {
                selectionchange: this.handleUserUtilBillCountRowSelect
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
            startField.setValue(Ext.Date.add(today, Ext.Date.DAY, -7));
            // The end is exclusive, so add a day
            endField.setValue(Ext.Date.add(today, Ext.Date.DAY, 1));
        }else{
            // Reload both stores, if the User has visited the reports tab
            // before and a date change event was not fired.
            this.getUserUtilBillCountsStore().reload();
            if(!this.getReportUtilityBillsGrid().isDisabled()){
                this.getUserUtilityBillsStore().reload();
            }
        }
    },

    /**
     * Handle the flagged bills sub-panel being activated.
     */
    handleFlaggedBillsActivate: function(){
        this.getAllFlaggedUtilityBillsStore().reload();
    },

    /**
     * Handle the selected date range changing
     */
    handleDateRangeChange: function() {
        var start = this.getStartDateField().getValue();
        var end = this.getEndDateField().getValue();
        var grid = this.getUserUtilBillCountGrid();
        if (start && end){
            var selections = grid.getSelectionModel().getSelection();
            if (selections.length){
                var userid = selections[0].get('id');
                this.updateUtilityBillsGrid(start, end, userid)
            }

            var store = this.getUserUtilBillCountsStore();
            store.getProxy().setExtraParam('start', start.toISOString());
            store.getProxy().setExtraParam('end', end.toISOString());
            store.reload()
        }
    },

    /**
     * Handle a user row becoming selected
     */
    handleUserUtilBillCountRowSelect: function(store, records ){
        var start = this.getStartDateField().getValue();
        var end = this.getEndDateField().getValue();
        if (records.length){
            var userid = records[0].get('id');
            this.updateUtilityBillsGrid(start, end, userid)
        }
    },

    /**
     *  Update the UtilityBills Grid
     */
    updateUtilityBillsGrid: function(start, end, userid){
        var grid = this.getReportUtilityBillsGrid();
        var store = this.getUserUtilityBillsStore();
        if(start && end && userid){
            store.getProxy().setExtraParam('start', start.toISOString());
            store.getProxy().setExtraParam('end', end.toISOString());
            store.getProxy().setExtraParam('id', userid);
            store.reload();
            grid.setDisabled(false);
        }else{
            grid.setDisabled(true);
        }
    }


});
