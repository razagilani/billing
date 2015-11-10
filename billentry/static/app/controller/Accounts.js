Ext.define('BillEntry.controller.Accounts', {
    extend: 'Ext.app.Controller',

    stores: [
        'Accounts',
        'AccountsMemory',
        'AccountsFilter',
        'Preferences'
    ],

    views:[
        'accounts.Accounts',
        'accounts.AccountForm',
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
                change: this.handleFilter
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
            scope: this
        });

        // Set up sorting & filtering
        this.getPreferencesStore().on({
            load: function(store, records, successful, eOpts ){
                // Update the store for sorts
                var memStore = this.getAccountsMemoryStore();
                var sortColumn = store.getOrCreate('default_account_sort_field', 'account').get('value');
                var sortDir = store.getOrCreate('default_account_sort_direction', 'DESC').get('value');

                memStore.sort({property: sortColumn, direction: sortDir});
                memStore.loadPage(1);
            },
            scope: this
        });

        this.getAccountsMemoryStore().on({
            beforeload: function(store, operation, eOpts){
                var prefStore = this.getPreferencesStore();
                var accountsStore = this.getAccountsStore();
                if(prefStore.count()!=0 && accountsStore.count()!=0){
                    // Filter
                    var filterStore = this.getAccountsFilterStore();
                    var allRecords = accountsStore.getRange();

                    // Find the correct filter record
                    var filterRecord = prefStore.getOrCreate('filtername', 'none');
                    var filter = filterStore.findRecord('value', filterRecord.get('value'));
                    if(filter == null){
                        filterRecord.set('value', 'none');
                        filter = filterStore.findRecord('value', 'none');
                    }
                    
                    // apply the filter
                    store.getProxy().data = Ext.Array.filter(allRecords, filter.get('filter').filterFn);
                    this.initFilterCombo();
                }
            },
            load: function(store, records, successful, eOpts ){
                var prefStore = this.getPreferencesStore();
                if(prefStore.count()!=0 && store.sorters.items.length){
                    // Sort
                    prefStore.setOrCreate('default_account_sort_field', store.sorters.items[0].property);
                    prefStore.setOrCreate('default_account_sort_direction', store.sorters.items[0].direction);
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
        if(store.count()!=0 && filterCombo){
            var filterPrefRec = store.findRecord('key', 'filtername');
            if(filterPrefRec){
                filterCombo.setValue(filterPrefRec.get('value'));
            }
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
        if(memStore.count()!=0 && prefStore.count()!=0 && newValue){
            var rec= prefStore.findRecord('key', 'filtername');
            rec.set('value', newValue);
            memStore.loadPage(1);
        }
    },

    /**
     * Get the next account number and add it populate the new account numnber field
     */
    loadNextAccountNumber: function() {
        var newAccountField = this.getAccountForm().down('textfield[name=account]');
        var store = this.getAccountsStore();

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
        if (accountForm.getForm().isValid()) {
            var values = accountForm.getForm().getValues();
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
                        accountsGrid.getSelectionModel().select([accountRec]);

                        var accountForm = this.getAccountForm();
                        accountForm.getForm().reset();
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
