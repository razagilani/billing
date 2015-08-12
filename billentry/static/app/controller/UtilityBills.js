Ext.define('BillEntry.controller.UtilityBills', {
    extend: 'Ext.app.Controller',

    stores: [
        'UtilityBills',
        'RateClasses',
        'Utilities',
        'Services',
        'Accounts',
        'Suppliers'
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
        ref: 'createExtractor',
        selector: '[action=createExtractor]',
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
            '[action=createExtractor]': {
                click: this.createExtractor
            },
            '[action=utilbillHelp]': {
                click: this.handleUtilbillHelp
            },
            '#utility_combo':{
                focus: this.handleUtilityComboFocus,
                blur: this.handleUtilityBlur
            },
           '#rate_class_combo': {
                expand: this.handleRateClassExpand,
                focus: this.handleRateClassComboFocus,
                blur: this.handleRateClassBlur
            },
            '#supplier_combo': {
                focus: this.handleSupplierComboFocus,
                blur: this.handleSupplierBlur
            },
            '#service_combo': {
                blur: this.handleServiceComboBlur
            },
            '#flagged': {
                beforecheckchange: this.handleCheckChange
            },
            '#tou': {
                beforecheckchange: this.handleCheckChange
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


    /**
     * Handle filtering rate_class combo on the utility of currently selected row
     * When rate_class combo is selected in the UI
     */
    handleRateClassComboFocus: function(combo) {
        var utility_grid = combo.findParentByType('grid');
        var selected = utility_grid.getSelectionModel().getSelection()[0];
        combo.setRawValue(selected.get('rate_class'));
    },

    /*
     * creates a new rate_class when the rate_class combo box loses focus
     */
    handleRateClassBlur: function(combo, event, opts){
        var rateClassStore = this.getRateClassesStore();
        var selected = combo.findParentByType('grid').getSelectionModel().getSelection()[0];
        if (rateClassStore.findRecord('id', combo.getValue()) === null){
            var utilBillsStore = this.getUtilityBillsStore();
            utilBillsStore.suspendAutoSync();
            rateClassStore.suspendAutoSync();
            rateClassStore.add({name: combo.getRawValue(),
                               utility_id: selected.get('utility_id'),
                               service: selected.get('service')});
            rateClassStore.sync({
                success: function(batch, options){
                    this.getUtilityBillsStore().resumeAutoSync();
                    selected.set('rate_class_id', batch.operations[0].records[0].get('id'));
                },
                failure: function(){
                    this.getUtilityBillsStore().resumeAutoSync();
                },
                scope: this
            });
            rateClassStore.resumeAutoSync();
        }
    },

    /**
     * Displays the rate classes related with the currently selected utility
     */
    handleRateClassExpand: function(combo, record, index){
        var utility_grid = combo.findParentByType('grid');
        var selected = utility_grid.getSelectionModel().getSelection()[0];
        var rate_class_store = Ext.getStore('RateClasses');
        rate_class_store.clearFilter(true);
        rate_class_store.filter({property:"utility_id", type: 'int',
                                    value: selected.get('utility_id'),
                                    exactMatch:true});
    },

    /**
     * Handle reloading utility bills tore when service combo loses focus
     */
    handleServiceComboBlur: function(combo){
        var utility_bill_grid = combo.findParentByType('grid');
        utility_bill_grid.getStore().reload();
        utility_bill_grid.getView().refresh();
    },

    /**
     * Handle updating flagged and tou checkboxes in the UI
     * Disables editing these two check boxes if the currently
     * selected row is marked as entered
     */
    handleCheckChange: function(checkbox, rowIndex, checked, eOpts ){
        var utility_bills_grid = this.getUtilityBillsGrid();
        if (checkbox.itemId == 'flagged' || checkbox.itemId=='tou')
        {
            row = utility_bills_grid.getStore().getAt(rowIndex);
            if (row.get('processed') || row.get('entered'))
            {
                Ext.MessageBox.show({
                            title: 'Entered Record Cannot be edited',
                            msg: 'Please clear the entered checkbox before editing this record',
                            buttons: Ext.MessageBox.OK
                                    });
                return false;
            }
        }
    },

    /*
     * creates a new utility when the utility combo box loses focus
     */
    handleUtilityBlur: function(combo, event, opts){
        var utilityStore = this.getUtilitiesStore();
        if (combo.getRawValue() == '') {
            utilityStore.rejectChanges();
            this.getUtilityBillsStore().rejectChanges();
            return;
        }
        var selected = combo.findParentByType('grid').getSelectionModel().getSelection()[0];
        if (utilityStore.findRecord('id', combo.getValue()) === null){
            var utilBillsStore = this.getUtilityBillsStore();
            utilBillsStore.suspendAutoSync();
            utilityStore.suspendAutoSync();
            var supply_group_id = utilBillsStore.findRecord('id', selected.get('id')).get('supply_group_id');
            utilityStore.add({name: combo.getRawValue(),
                                 sos_supply_group_id: supply_group_id});
            utilityStore.sync({
                success: function(batch, options){
                    this.getUtilityBillsStore().resumeAutoSync();
                    selected.set('utility_id', batch.operations[0].records[0].get('id'));
                },
                failure: function(){
                    this.getUtilityBillsStore().resumeAutoSync();
                },
                scope: this
            });
            utilityStore.resumeAutoSync();
        }
    },

    /**
     * displays the name from utility store for the currently selected
     * utility as utility is an object containing name and Id's.
     */
    handleUtilityComboFocus: function(combo) {
        var utility_grid = combo.findParentByType('grid');
        var selected = utility_grid.getSelectionModel().getSelection()[0];
        combo.setRawValue(selected.get('utility'));
    },

    /**
     * displays the name from supplier store for the currently selected
     * supplier as supplier is an object containing name and Id's.
     */
    handleSupplierComboFocus: function(combo) {
        var utility_grid = combo.findParentByType('grid');
        var selected = utility_grid.getSelectionModel().getSelection()[0];
        combo.setRawValue(selected.get('supplier'));
    },

    /*
     * creates a new supplier when the supplier combo box loses focus
     */
    handleSupplierBlur: function(combo, event, opts){
        var supplierStore = this.getSuppliersStore();
        var selected = combo.findParentByType('grid').getSelectionModel().getSelection()[0];
        if (supplierStore.findRecord('id', combo.getValue()) === null){
            var utilBillsStore = this.getUtilityBillsStore();
            utilBillsStore.suspendAutoSync();
            supplierStore.suspendAutoSync();
            Ext.MessageBox.confirm("Confirmation", "Do you want to create a new supplier named "+ combo.getRawValue() + "?",
                   function(btnText){
                        if(btnText === "yes"){
                            supplierStore.add({name: combo.getRawValue()});
                            supplierStore.sync({
                                success: function(batch, options){
                                    utilBillsStore.resumeAutoSync();
                                    selected.set('supplier_id', batch.operations[0].records[0].get('id'));
                                },
                                failure: function(){
                                    utilBillsStore.resumeAutoSync();
                                },
                            scope: this});
                            supplierStore.resumeAutoSync();
                        }
                        else{
                            combo.reset();
                            utilBillsStore.rejectChanges();
                            utilBillsStore.resumeAutoSync();
                            supplierStore.resumeAutoSync();
                        }
                   });
        }
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
     * to the index of the currently selected record.
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

    /* Create a new extractor with the currently selected bill. 
     This opens the /create-extractor/ page. 
    */
    createExtractor: function(){
        var selected = this.getUtilityBillsGrid().getSelectionModel().getSelection()[0];
        var bill_arg = "";
        if (selected != null){
            bill_arg = "?bill_id="+selected.get('id');
        }
        window.open('/create-extractor/#/settings'+bill_arg);
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
