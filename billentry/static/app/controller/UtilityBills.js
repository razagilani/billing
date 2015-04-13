Ext.define('BillEntry.controller.UtilityBills', {
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
    },{
        ref: 'utilbillHelp',
        selector: '[action=utilbillHelp]'
    }],
    
    init: function() {
        this.getUtilityBillsStore().on({
        beforesync: this.checkService,
        scope: this
        });

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
            '[action=utilbillHelp]': {
                click: this.handleUtilbillHelp
            },
            '#utility_combo':{
                select: this.handleUtilityComboChanged
            },
           '#rate_class_combo': {
                focus: this.handleRateClassComboFocus
            },
            '#service_combo': {
                blur: this.handleServiceComboBlur
            }
        });

        // This assures that there is never no account selected
        this.getAccountsStore().on('load', function() {
            this.getAccountsGrid().getSelectionModel().select(0);
        }, this, {single: true});

        this.getUtilityBillsStore().on('write', function(store, operation){
            var utilityAccountId = operation.records[0].get('utility_account_id');

            // Find the accounts record associated with the updated utility bill
            var accountsRecord = this.getAccountsStore().findRecord('id', utilityAccountId);
            console.log(accountsRecord);

            // This request will not actually change the state on the server. However, it will cause the server to
            // reavaluate 'bills_to_be_entered' for this account record.
            accountsRecord.set('bills_to_be_entered', !accountsRecord.get('bills_to_be_entered'));
        }, this);

        this.getAccountsStore().on('write', function(store){
            // Refresh filters
            var filters = store.filters.items;
            store.clearFilter(true);
            Ext.Array.each(filters, function(filter){
                store.filter(filter);
            });
        });
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
            if (selected.get('meter_identifier') == '')
            {
                row_index = this.getUtilityBillsStore().indexOf(selected);
                last_row = this.getUtilityBillsStore().getAt(row_index-1);
                if (last_row != null)
                    selected.set('meter_identifier', last_row.get('meter_identifier'))
            }
        }
    },

    checkService: function(options, eOpts){
        service = options.update[0].get('service');
        rate_class = options.update[0].get('rate_class');
        if ((service =='Gas' || service =='Electric') && rate_class=='Unknown') {
            Ext.MessageBox.show({
                title: 'Invalid RateClass',
                msg: 'Please select a Rate Class before selecting service!',
                buttons: Ext.MessageBox.OK
            });

            return false;
        }
        if(rate_class=='')
        {
            Ext.MessageBox.show({
                title: 'Invalid RateClass',
                msg: 'Rate Class cannot be empty',
                buttons: Ext.MessageBox.OK
            });
            this.getUtilityBillsStore().reload();
            return false;
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
        rate_classes_store.filter({property:"utility_id", type: 'int',
                                    value: utility.get('id'), exactMatch:true});
    },

    handleServiceComboBlur: function(combo){
        var utility_bill_grid = combo.findParentByType('grid');
        utility_bill_grid.getStore().reload();
        utility_bill_grid.getView().refresh();
    },

    handleUtilityComboChanged: function(utility_combo, record){
        var rate_class_store = Ext.getStore("RateClasses");
        rate_class_store.clearFilter(true);
        rate_class_store.filter({property:"utility_id", type: 'int',
                                    value: record[0].get('id'), exactMatch:true});
        var selected = this.getUtilityBillsGrid().getSelectionModel().getSelection()[0];
        var utility_store = this.getUtilityBillsStore();
        if (rate_class_store.count() > 0)
            selected.set('rate_class', rate_class_store.getAt(0).get('name'));
        else
            selected.set('rate_class', null)
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
    },

    handleUtilbillHelp: function(){
        var margin = 35;
        var width = 850;
        var store = this.getUtilityBillsStore();
        var win = Ext.create('Ext.window.Window', {
            overflowY: 'auto',
            width: width,
            height: Ext.getBody().getViewSize().height - margin * 2,
            title: "Utility Bill Help",
            layout: 'fit',
            items: [{
                xtype : "component",
                autoEl : {
                    tag : "iframe",
                    src : store.getAt(0).get('wiki_url')
                }
            }]
        });
        win.show();
        win.setPosition(Ext.getBody().getViewSize().width - width - margin, margin);
    }
});
