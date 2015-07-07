Ext.define('ReeBill.controller.UtilityBillRegisters', {
    extend: 'Ext.app.Controller',

    stores: [
        'UtilityBillRegisters'
    ],

    views: [
        'metersandregisters.UtilityBillRegisters',
        'metersandregisters.TOUMetering'
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
        ref: 'newUtilityBillRegisterButton',
        selector: 'button[action=newUtilityBillRegister]'
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
            beforesync: this.updateTOUSliders,
            scope: this
        })

    },

    /**
     * Handle the panel being activated.
     */
    handleActivate: function() {
        var selectedBill = this.getUtilityBillsGrid().getSelectionModel().getSelection();
        var processed = selectedBill[0].get('processed');
        this.getNewUtilityBillRegisterButton().setDisabled(processed);
        var store = this.getUtilityBillRegistersStore();

        if (!selectedBill.length)
            return;

        store.getProxy().extraParams = {
            utilbill_id: selectedBill[0].get('id')
        };
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

        store.add({
            identifier:'Enter Register ID',
            meter_identifier:'Enter Meter ID',
            description: 'Insert description',
            quantity: 0,
            reg_type: 'total',
            register_binding: 'REG_TOTAL',
            unit: 'therms',
            utilbill_id: selectedBill[0].internalId
        });
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
        var warningLabel = this.getTOUWarningLabel();

        // Reset the panel
        warningLabel.setVisible(false);
        panel.setDisabled(false);
        weekday.removeThumbs();
        weekend.removeThumbs();

        var peakReg = store.findRecord('register_binding', 'REG_PEAK');
        var intReg = store.findRecord('register_binding', 'REG_INTERMEDIATE');
        var offPeakReg = store.findRecord('register_binding', 'REG_OFFPEAK');
        if(peakReg === null || offPeakReg === null){
            panel.setDisabled(true);
            return
        }

        // Thumbs have to be created in order from left to right
        // to function properly

        // Offpeak - Early Intermediate
        var periods;
        if(intReg !== null){
            periods = intReg.get('active_periods');
            if(periods === null){
                warningLabel.setVisible(true);
                weekday.addThumb(5);
                weekend.addThumb(5);
            }else{
                weekday.addThumb(periods.active_periods_weekday[0][0]);
                weekend.addThumb(periods.active_periods_weekend[0][0]);
            }
        }

        // Early Intermediate - Peak
        periods = peakReg.get('active_periods');
        if(periods === null){
            warningLabel.setVisible(true);
            weekday.addThumb(9);
            weekend.addThumb(9);
        }else{
            weekday.addThumb(periods.active_periods_weekday[0][0]);
            weekend.addThumb(periods.active_periods_weekend[0][0]);
        }

        // Peak - Late Intermediate
        if(intReg !== null){
            if(intReg.get('active_periods') === null){
                warningLabel.setVisible(true);
                weekday.addThumb(17);
                weekend.addThumb(17);
            }else{
                weekday.addThumb(periods.active_periods_weekday[0][1]);
                weekend.addThumb(periods.active_periods_weekend[0][1]);
            }
        }

        // Late Intermediate - Offpeak
        periods = offPeakReg.get('active_periods');
        if(periods === null){
            warningLabel.setVisible(true);
            weekday.addThumb(21);
            weekend.addThumb(21);
        }else{
            weekday.addThumb(periods.active_periods_weekday[1][0]);
            weekend.addThumb(periods.active_periods_weekend[1][0]);
        }
    },

    handleSaveTOU: function(){
        var store = this.getUtilityBillRegistersStore();
        var weekday = this.getTOUWeekdaySlider();
        var weekend = this.getTOUWeekendSlider();
        var peakReg = store.findRecord('register_binding', 'REG_PEAK');
        var intReg = store.findRecord('register_binding', 'REG_INTERMEDIATE');
        var offPeakReg = store.findRecord('register_binding', 'REG_OFFPEAK');

        if(peakReg === null || offPeakReg === null){
            return
        }


        store.suspendAutoSync();
        // The Server expects the following format for each register
        var peak_periods = {
            active_periods_weekday: null,
            active_periods_weekend: null,
        };
        var offpeak_periods = {
            active_periods_weekday: null,
            active_periods_weekend: null,
        };
        var int_periods = {
            active_periods_weekday: null,
            active_periods_weekend: null,
        };

        var weekday_values = weekday.getValues();
        var weekend_values = weekend.getValues();

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
            // Intermediate is first thumb - second thumb & third thumb - last thumb
            int_periods.active_periods_weekday = [
                [weekday_values[0],weekday_values[1]],
                [weekday_values[2],weekday_values[3]]
            ];
            int_periods.active_periods_weekend = [
                [weekend_values[0],weekend_values[1]],
                [weekend_values[2],weekend_values[3]]
            ];
            // Peak is second thumb - third thumb
            peak_periods.active_periods_weekday = [
                [weekday_values[1],weekday_values[2]]
            ];
            peak_periods.active_periods_weekend = [
                [weekend_values[1],weekend_values[2]]
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
            // Peak is first thumb - second thumb
            peak_periods.active_periods_weekday = [
                [weekday_values[0],weekday_values[1]]
            ];
            peak_periods.active_periods_weekend = [
                [weekend_values[0],weekend_values[1]]
            ];
            peakReg.set('active_periods', peak_periods);
            offPeakReg.set('active_periods', offpeak_periods);
        }
        // Sync everything at once & reenable autosync
        store.sync();
        store.resumeAutoSync();
    }

});
