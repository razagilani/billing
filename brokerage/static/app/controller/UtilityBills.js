Ext.define('ReeBill.controller.UtilityBills', {
    extend: 'Ext.app.Controller',

    stores: [
        'UtilityBills',
        'RateClasses',
        'Utilities',
        'Services',
        'Accounts'
    ],

    views: [
        'utilitybills.UtilityBills'    ],
    
    refs: [{
        ref: 'uploadUtilityBillForm',
        selector: 'uploadUtilityBill'
    },{
        ref: 'accountsGrid',
        selector: 'grid[id=accountsGrid]'
    }, {
        ref: 'utilityBillsGrid',
        selector: 'grid[id=utilityBillsGrid]'
    },{
        ref: 'accountLabel',
        selector: '[id=utilbillAccountLabel]'
    },{
        ref: 'utilbillPrevious',
        selector: '[action=utilbillPrevious]'
    },{
        ref: 'utilbillNext',
        selector: '[action=utilbillNext]'
    }],
    
    init: function() {
        this.application.on({
            scope: this
        });

        this.control({
            'grid[id=utilityBillsGrid]': {
                selectionchange: this.handleRowSelect
            },
            'grid[id=accountsGrid]': {
                selectionchange: this.handleAccountRowSelect
            },
            'panel[name=utilityBillsTab]': {
                activate: this.handleActivate
            },
            '[action=utilbillPrevious]': {
                click: this.decrementAccount
            },
            '[action=utilbillNext]': {
                click: this.incrementAccount
            },
            '#rate_class_combo': {
                focus: this.handleRateClassComboFocus
            }
        });

        // This assures that there is never no account selected
        this.getAccountsStore().on('load', function() {
            this.getAccountsGrid().getSelectionModel().select(0);
        }, this, {single: true});
    },

    /**
     * Handle the row selection.
     */
    handleRowSelect: function(combo, recs) {
        var selected = this.getUtilityBillsGrid().getSelectionModel().getSelection()[0];
        if (selected != null) {
            var chargesStore = Ext.getStore("Charges");
            var proxy = chargesStore.getProxy();
            proxy.extraParams = {utilbill_id: selected.get('id')};
            chargesStore.reload();
        }
    },

    /**
     * Handle the utility bill panel being activated.
     */
    handleActivate: function() {
        var store = this.getUtilityBillsStore();
        store.reload();
    },

    /**
     * Handle a row in the acounts panel being selected.
     * In the future this might move into its own controller
     */
    handleAccountRowSelect: function(selectionModel, records) {
        this.setButtonsDisabled(this.getAccountsStore().indexOf(records[0]));
        this.updateCurrentAccountId(records[0]);
    },

    handleRateClassComboFocus: function(combo) {
        var utility_bill_grid = combo.findParentByType('grid');
        var selected = utility_bill_grid.getSelectionModel().getSelection()[0];
        var utilities_store = this.getUtilitiesStore();
        var utility = utilities_store.findRecord('name', selected.get('utility'));
        var rate_classes_store = this.getRateClassesStore();
        rate_classes_store.clearFilter(true);
        rate_classes_store.filter('utility_id', utility.get('id'));
    },

    /**
     * Finds the store index of the record that is offset by 'offset' from
     * the currently selected record
     */
    moveIndex: function(offset) {
        var accountStore = this.getAccountsStore();
        var accountGrid = this.getAccountsGrid();
        var selectedRecord = accountGrid.getSelectionModel().getSelection()[0];
        var recordIndex = accountStore.indexOf(selectedRecord);
        return recordIndex + offset;
    },

    /* Update disabled/enabled state of "Previous" and "Next" buttons according
     to the index of the currently selected record.
     */
    setButtonsDisabled: function(newRecordIndex) {
        this.getUtilbillPrevious().setDisabled(newRecordIndex === 0);
        this.getUtilbillNext().setDisabled(
                newRecordIndex === this.getAccountsStore().count() - 1);
    },

    /* Select previous row in acocunt grid and reload the grid.
     */
    decrementAccount: function() {
        var newRecordIndex = this.moveIndex(-1);
        this.setButtonsDisabled(newRecordIndex);
        var newRecord = this.getAccountsStore().getAt(newRecordIndex);
        this.getAccountsGrid().getSelectionModel().select(newRecord);
    },

    /* Select next row in acocunt grid and reload the grid.
     */
    incrementAccount: function() {
        var newRecordIndex = this.moveIndex(1);
        this.setButtonsDisabled(newRecordIndex);
        var newRecord = this.getAccountsStore().getAt(newRecordIndex);
        this.getAccountsGrid().getSelectionModel().select(newRecord);
    },

    /**
     * Updates the labels indicating the currently selected account on the
     * utility bill grid
     */
    updateCurrentAccountId: function(selectedAccountRecord) {
        var id = selectedAccountRecord.get('id');
        var nextility_account_number = selectedAccountRecord.get('account');
        this.getAccountLabel().setText(id + ' ' + nextility_account_number);
        var store = this.getUtilityBillsStore();
        store.getProxy().setExtraParam('id', id);
        store.reload();
    }
});
