Ext.define('ReeBill.controller.UtilityBillRegisters', {
    extend: 'Ext.app.Controller',

    stores: [
        'UtilityBillRegisters'
    ],
    
    refs: [{
        ref: 'utilityBillRegistersGrid',
        selector: 'grid[id=utilityBillRegistersGrid]'
    },{
        ref: 'accountsGrid',
        selector: 'grid[id=accountsGrid]'
    },{
        ref: 'utilityBillsGrid',
        selector: 'grid[id=utilityBillsGrid]'
    },{
        ref: 'removeUtilityBillRegisterButton',
        selector: 'button[action=removeUtilityBillRegister]'
    },{
        ref: 'TOUWeekdaySlider',
        selector: 'multislider[id=TOUMeteringSliderWeekdays]'
    },{
        ref: 'TOUWeekendSlider',
        selector: 'multislider[id=TOUMeteringSliderWeekends]'
    },{
        ref: 'TOUHolidaySlider',
        selector: 'multislider[id=TOUMeteringSliderHolidays]'
    },{
        ref: 'TOUPanel',
        selector: '[id=TOUMeteringForm]'
    },{
        ref: 'TOUWarningLabel',
        selector: 'label[id=TOUMeteringWarningLabel]'
    }],

    init: function() {
        var me = this,
            store = me.getUtilityBillRegistersStore();

        this.application.on({
            scope: this
        });
        
        this.control({
            'panel[name=metersTab]': {
                activate: this.handleActivate
            },
            'grid[id=utilityBillRegistersGrid]': {
                selectionchange: this.handleRowSelect
            },
            'button[action=newUtilityBillRegister]': {
                click: this.handleNew
            },
            'button[action=removeUtilityBillRegister]': {
                click: this.handleDelete
            },
            'button[action=saveTOUMetering]': {
                click: this.handleSaveTOU
            }
        });

        store.on({
            load: this.updateTOUSliders,
            sync: this.updateTOUSliders,
            scope: this
        })

    },

    /**
     * Handle the panel being activated.
     */
    handleActivate: function() {
        var selectedBill = this.getUtilityBillsGrid().getSelectionModel().getSelection();
        var store = this.getUtilityBillRegistersStore();

        if (!selectedBill.length)
            return;

        var params = {
            utilbill_id: selectedBill[0].get('id')
        }

        store.getProxy().extraParams = params;
        store.load();
    },

    /**
     * Handle the row selection.
     */
    handleRowSelect: function() {
        var hasSelections = this.getUtilityBillsGrid().getSelectionModel().getSelection().length > 0;

        this.getRemoveUtilityBillRegisterButton().setDisabled(!hasSelections);
    },

    /**
     * Handle the new utitlity bill button being clicked.
     */
    handleNew: function() {
        var store = this.getUtilityBillRegistersStore(),
            selectedAccount = this.getAccountsGrid().getSelectionModel().getSelection(),
            selectedBill = this.getUtilityBillsGrid().getSelectionModel().getSelection();

        if (!selectedAccount || !selectedAccount.length || !selectedBill || !selectedBill.length)
            return;

        store.add({identifier:'new Register',
                   meter_identifier:'new Meter'})

    },

    /**
     * Handle the delete utitlity bill button being clicked.
     */
    handleDelete: function() {
        var store = this.getUtilityBillRegistersStore(),
            selectedAccount = this.getAccountsGrid().getSelectionModel().getSelection(),
            selectedBill = this.getUtilityBillsGrid().getSelectionModel().getSelection(),
            selectedUtilityBillRegister = this.getUtilityBillRegistersGrid().getSelectionModel().getSelection();

        if (!selectedAccount || !selectedAccount.length || !selectedBill || !selectedBill.length
                || !selectedUtilityBillRegister || !selectedUtilityBillRegister.length)
            return;

        store.remove(selectedUtilityBillRegister);
    },

    updateTOUSliders: function(){
        var store = this.getUtilityBillRegistersStore();
        var panel = this.getTOUPanel();
        var weekday = this.getTOUWeekdaySlider();
        var weekend = this.getTOUWeekendSlider();
        var holiday = this.getTOUHolidaySlider();
        var warningLabel = this.getTOUWarningLabel();

        // Reset the panel
        warningLabel.setVisible(false);
        panel.setDisabled(false);
        weekday.removeThumbs();
        weekend.removeThumbs();
        holiday.removeThumbs();

        var peakReg = store.findRecord('register_binding', 'REG_PEAK');
        var intReg = store.findRecord('register_binding', 'REG_INTERMEDIATE');
        var offPeakReg = store.findRecord('register_binding', 'REG_OFFPEAK');
        console.log(peakReg, intReg, offPeakReg);
        if(peakReg === null || offPeakReg === null){
            panel.setDisabled(true);
            return
        }

        // Thumbs have to be created in order from left to right
        // to function properly

        // Offpeak - Early Intermediate
        if(intReg !== null){
            if(intReg.get('active_periods') === null){
                warningLabel.setVisible(true);
                weekday.addThumb(5);
                weekend.addThumb(5);
                holiday.addThumb(5);
            }
        }

        // Early Intermediate - Peak
        if(peakReg.get('active_periods') === null ||
            offPeakReg.get('active_periods') === null){
            warningLabel.setVisible(true);
            weekday.addThumb(9);
            weekend.addThumb(9);
            holiday.addThumb(9);
        }

        // Peak - Late Intermediate
        if(peakReg.get('active_periods') === null ||
            offPeakReg.get('active_periods') === null){
            weekday.addThumb(17);
            weekend.addThumb(17);
            holiday.addThumb(17);
        }

        // Late Intermediate - Offpeak
        if(intReg !== null){
            if(intReg.get('active_periods') === null){
                warningLabel.setVisible(true);
                weekday.addThumb(21);
                weekend.addThumb(21);
                holiday.addThumb(21);
            }
        }
    },

    handleSaveTOU: function(){
        var store = this.getUtilityBillRegistersStore();
        var weekday = this.getTOUWeekdaySlider();
        var weekend = this.getTOUWeekendSlider();
        var holiday = this.getTOUHolidaySlider();
        var peakReg = store.findRecord('register_binding', 'REG_PEAK');
        var intReg = store.findRecord('register_binding', 'REG_INTERMEDIATE');
        var offPeakReg = store.findRecord('register_binding', 'REG_OFFPEAK');
        console.log(weekday.getValues(), weekend.getValues(), holiday.getValues());

        if(peakReg === null || offPeakReg === null){
            return
        }

        // The Server expects the following format for each register
        var peak_periods = {
            active_periods_weekday: null,
            active_periods_weekend: null,
            active_periods_holiday: null
        };
        var offpeak_periods = {
            active_periods_weekday: null,
            active_periods_weekend: null,
            active_periods_holiday: null
        };
        var int_periods = {
            active_periods_weekday: null,
            active_periods_weekend: null,
            active_periods_holiday: null
        };

        var weekday_values = weekday.getValues();
        var weekend_values = weekend.getValues();
        var holiday_values =holiday.getValues();

        if(intReg !== null){
            // There are 4 thumbs
            // Offpeak is 0 - first thumb & last thumb - 23
            offpeak_periods.active_periods_weekday = [
                [0,weekday_values[0]],
                [weekday_values[3],23]
            ];
            offpeak_periods.active_periods_weekend = [
                [0,weekend_values[0]],
                [weekend_values[3],23]
            ];
            offpeak_periods.active_periods_holiday = [
                [0,holiday_values[0]],
                [holiday_values[3],23]
            ];
            // Intermediate is first thumb - second thumb & third thumb - last thumb
            int_periods.active_periods_weekday = [
                [weekday_values[0],weekday_values[1]],
                [weekday_values[2],weekday_values[3]]
            ];
            int_periods.active_periods_weekend = [
                [weekend_values[0],weekend_values[1]],
                [weekend_values[2],weekend_values[3]]
            ];
            int_periods.active_periods_holiday = [
                [holiday_values[0],holiday_values[1]],
                [holiday_values[2],holiday_values[3]]
            ];
            // Peak is second thumb - third thumb
            peak_periods.active_periods_weekday = [
                [weekday_values[1],weekday_values[2]]
            ];
            peak_periods.active_periods_weekend = [
                [weekend_values[1],weekend_values[2]]
            ];
            peak_periods.active_periods_holiday = [
                [holiday_values[1],holiday_values[2]]
            ];
            peakReg.set('active_periods', peak_periods);
            intReg.set('active_periods', int_periods);
            offPeakReg.set('active_periods', offpeak_periods);
        }else{
            // There are 2 thumbs
            // Offpeak is 0 - first thumb & last thumb - 23
            offpeak_periods.active_periods_weekday = [
                [0,weekday_values[0]],
                [weekday_values[1],23]
            ];
            offpeak_periods.active_periods_weekend = [
                [0,weekend_values[0]],
                [weekend_values[1],23]
            ];
            offpeak_periods.active_periods_holiday = [
                [0,holiday_values[0]],
                [holiday_values[1],23]
            ];
            // Peak is first thumb - second thumb
            peak_periods.active_periods_weekday = [
                [weekday_values[0],weekday_values[1]]
            ];
            peak_periods.active_periods_weekend = [
                [weekend_values[0],weekend_values[1]]
            ];
            peak_periods.active_periods_holiday = [
                [holiday_values[0],holiday_values[1]]
            ];
            peakReg.set('active_periods', peak_periods);
            offPeakReg.set('active_periods', offpeak_periods);
        }
        console.log(offpeak_periods, int_periods, peak_periods);
    }

});
