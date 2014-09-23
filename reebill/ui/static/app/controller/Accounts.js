Ext.define('ReeBill.controller.Accounts', {
    extend: 'Ext.app.Controller',

    stores: [
        'Accounts', 'AccountsMemory', 'AccountsFilter', 'Preferences'
    ],
    
    refs: [{
        ref: 'accountForm',
        selector: 'accountForm'
    },{
        ref: 'accountsGrid',
        selector: 'grid[id=accountsGrid]'
    },{
        ref: 'accountsFilter',
        selector: 'combo[name=accountsFilter]'
    }],    
    
    init: function() {
        this.application.on({
            scope: this
        });
        
        this.control({
            'panel[name=accountsTab]': {
                activate: this.handleActivate
            },
            'accountForm': {
                expand: this.loadNextAccountNumber
            },
            'grid[id=accountsGrid]': {
                selectionchange: this.handleAccountSelect
            },
            'button[action=saveNewAccount]': {
                click: this.saveNewAccount
            },
            'combo[name=accountsFilter]': {
                change: this.handleFilter,
                render: this.initFilterCombo
            }
        });

        this.getAccountsStore().on({
            beforeload: function(store){
                if(this.getAccountsGrid) {
                    var grid = this.getAccountsGrid();
                    grid.setLoading(true);
                }
            },
            load: function(store, records, successful, eOpts ){
                if(this.getAccountsGrid) {
                    var grid = this.getAccountsGrid();
                    grid.setLoading(false);
                }
            },
            add: function(){
                var accountForm = this.getAccountForm();
                accountForm.getForm().reset();
            },
            scope: this
        });

        // Set up sorting & filtering
        this.getPreferencesStore().on({
            load: function(store, records, successful, eOpts ){
                // Update the store for sorts
                var memStore = this.getAccountsMemoryStore();
                var sortColumn = store.getAt(store.find('key', 'default_account_sort_field')).get('value');
                var sortDir = store.getAt(store.find('key', 'default_account_sort_direction')).get('value');
                memStore.sort({property: sortColumn, direction: sortDir});
                memStore.loadPage(1);

                this.initFilterCombo();
            },
            scope: this
        });

        this.getAccountsMemoryStore().on({
            beforeload: function(store, operation, eOpts){
                var prefStore = this.getPreferencesStore();
                var accountsStore = this.getAccountsStore();
                if(prefStore.getRange().length && accountsStore.getRange().length){
                    // Filter
                    var filterStore = this.getAccountsFilterStore();
                    var allRecords = accountsStore.getRange();

                    // Find the correct filter record
                    var filterRecord = prefStore.getOrCreate('filtername', 'none')
                    var filter = filterStore.getAt(
                        filterStore.find('value',
                            filterRecord.get('value')));

                    // apply the filter
                    var filteredRecords = Ext.Array.filter(allRecords, filter.get('filter').filterFn)
                    store.getProxy().data = filteredRecords;
                }
            },
            load: function(store, records, successful, eOpts ){
                var prefStore = this.getPreferencesStore();
                var accountsStore = this.getAccountsStore();
                if(prefStore.getRange().length && accountsStore.getRange().length){
                    // Sort
                    var sortColumnRec = prefStore.getAt(prefStore.find('key', 'default_account_sort_field'));
                    var sortDirRec = prefStore.getAt(prefStore.find('key', 'default_account_sort_direction'));
                    sortColumnRec.set('value', store.sorters.items[0].property);
                    sortDirRec.set('value', store.sorters.items[0].direction);
                }
            },
            scope: this
        });
    },

    /**
     * Handle the panel being activated.
     */
    handleActivate: function() {
    },

    /**
     * Select the filter from preference store
     */
    initFilterCombo: function(){
        var store = this.getPreferencesStore();
        var filterCombo = this.getAccountsFilter();
        if(store.getRange().length && filterCombo){
            var filterPrefRec = store.getOrCreate('filtername', 'none');
            filterCombo.setValue(filterPrefRec.get('value'));
        }
    },

    /**
     * Handle the filter being changed.
     */
    handleFilter: function( combo, newValue, oldValue, eOpts) {
        // We're filtering every record, so we have to use AccountsStore
        // and not AccountsMemoryStore
        var memStore = this.getAccountsMemoryStore();
        var prefStore = this.getPreferencesStore();
        var filter = this.getAccountsFilter().getValue();
        var filterPrefRec = prefStore.setOrCreate('filtername', newValue);
        memStore.loadPage(1);
    },

    /**
     * Get the next account number and add it populate the new account numnber field
     */
    loadNextAccountNumber: function() {
        var newAccountField = this.getAccountForm().down('textfield[name=account]');
        var store = this.getAccountsStore()

        newAccountField.setValue(store.getNextAccountNumber());
    },

    /**
     * Save the new account.
     */
    saveNewAccount: function() {
        var accountForm = this.getAccountForm(),
            accountsGrid = this.getAccountsGrid(),
            makeAnotherAccount = accountForm.down('[name=makeAnotherAccount]').checked;
        var store = this.getAccountsStore();

        var memoryStore = this.getAccountsMemoryStore();
        memoryStore.on('load', function(){
                            console.log('memory store load')
        }, this);

        if (accountForm.getForm().isValid()) {
            var values = accountForm.getForm().getValues();
            console.log(values);

            store.suspendAutoSync();
            store.add(values);
            if (!makeAnotherAccount) {
                store.sync({
                    success: function (batch, options) {
                        var filter = this.getAccountsFilter().getValue();
                        var filterStore = this.getAccountsFilterStore();
                        var filterRec = filterStore.findRecord('value', filter);
                        var accountRec = batch.operations[0].records[0];
                        var memoryStore = this.getAccountsMemoryStore();
                        var accountsStore = this.getAccountsStore();
                        console.log('batch:', batch, options, filter, filterRec, accountRec);

                        // Test if the current filter would filter out the newly
                        // created account and if yes, set the filter to none
                        if(!filterRec.get('filter').filterFn(accountRec)){
                            var noneFilter = filterStore.findRecord('value', 'none');
                            var filterCombo = this.getAccountsFilter();
                            filterCombo.select(noneFilter);
                        }

                        memoryStore.sort({
                            property: 'account',
                            direction: 'DESC'
                        });
                        memoryStore.loadPage(1);
                    },
                    callback: function(){
                        store.resumeAutoSync();
                    },
                    scope: this
                });
                accountsGrid.expand();
            }else {
                this.loadNextAccountNumber();
                store.sync({
                    callback: function(){
                        store.resumeAutoSync();
                    },
                    scope: this
                });
            }
        }
    },

    /**
     * Handle the account selection.
     */
    handleAccountSelect: function() {

    }

});
