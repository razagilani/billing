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
                change: this.handleFilter
            }
        });

        this.getAccountsStore().on({
            load: function(store, records, successful, eOpts ){
                var memoryStore = this.getAccountsMemoryStore();
                memoryStore.loadPage(1);
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

                // Update the filter combofield for filters
                var filterCombo = this.getAccountsFilter();
                var filterPrefRecId = store.find('key', 'filtername')
                if( filterPrefRecId !== -1){
                    filterCombo.setValue(
                        store.getAt(filterPrefRecId).get('value'));
                }else {
                    filterCombo.setValue('none')
                }
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
                    var filterRecordId = prefStore.find('key', 'filtername');
                    if (filterRecordId !== -1){
                        var filtername = prefStore.getAt(filterRecordId).get('value');
                    }else{
                        var filtername = 'none'
                    }
                    var filter = filterStore.getAt(filterStore.find('value', filtername));

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
     * Handle the filter being changed.
     */
    handleFilter: function( combo, newValue, oldValue, eOpts) {
        // We're filtering every record, so we have to use AccountsStore
        // and not AccountsMemoryStore
        var memStore = this.getAccountsMemoryStore()
        var prefStore = this.getPreferencesStore();
        var filter = this.getAccountsFilter().getValue();
        var filterPrefRecId = prefStore.find('key', 'filtername')
        if( filterPrefRecId !== -1){
            var prefRec = prefStore.getAt(filterPrefRecId).set('value', newValue);
        }else{
            prefStore.add({key: 'filtername', value: newValue});
        }
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
            makeAnotherAccount = accountForm.down('[name=makeAnotherAccount]');
        var store = this.getAccountsStore()

        if (accountForm.getForm().isValid()) {
            var values = accountForm.getForm().getValues();
            console.log(values);

            store.add(values);
            if (!makeAnotherAccount.getValue())
                accountsGrid.expand();
            else
                this.loadNextAccountNumber();
        }
    },

    /**
     * Handle the account selection.
     */
    handleAccountSelect: function() {

    }

});
