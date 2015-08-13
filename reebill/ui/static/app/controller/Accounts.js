Ext.define('ReeBill.controller.Accounts', {
    extend: 'Ext.app.Controller',

    stores: [
        'Accounts',
        'AccountsFilter',
        'Preferences'
    ],

    views:[
        'accounts.Accounts',
        'accounts.AccountForm',
        'accounts.AccountEditForm'
    ],

    refs: [{
        ref: 'accountForm',
        selector: 'accountForm'
    },{
        ref: 'accountEditForm',
        selector: 'accountEditForm'
    },{
        ref: 'accountsGrid',
        selector: 'grid[id=accountsGrid]'
    },{
        ref: 'accountsFilter',
        selector: 'combo[name=accountsFilter]'
    },{
        ref: 'mergeBtn',
        selector: 'button#mergeAccountRecord'
    },{
        ref: 'editBtn',
        selector: 'button#editAccountRecord'
    },{
        ref: 'newAccountBtn',
        selector: 'button#createNewAccount'
    },{
        ref: 'newAccountBtn',
        selector: 'button#createNewAccount'
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
                beforerender: this.loadNextAccountNumber
            },
            'grid[id=accountsGrid]': {
                selectionchange: this.handleAccountSelect
            },
            'button[action=saveNewAccount]': {
                click: this.saveNewAccount
            },
            'button[action=saveEditChanges]': {
                click: this.saveEditChanges
            },
            'combo[name=accountsFilter]': {
                change: this.handleFilter
            },
            '[action=mergeRecords]': {
                click: this.handleMerge
            },
            'button[action=editRecord]': {
                click: this.handleEdit
            },
            'button[action=createAccount]': {
                click: this.handleCreateAccount
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
                var memStore = this.getAccountsStore();
                var sortColumn = store.getOrCreate('default_account_sort_field', 'account').get('value');
                var sortDir = store.getOrCreate('default_account_sort_direction', 'DESC').get('value');

                memStore.sort({property: sortColumn, direction: sortDir});
                memStore.loadPage(1);
            },
            scope: this
        });

        this.getAccountsStore().on({
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
     * Handle Create Account button
     */
    handleCreateAccount: function(){
        var createAccountWindow = Ext.create('Ext.window.Window', {
            title: 'Accounts',
            closeAction: 'destroy',
            id: 'createAccountWindow',
            items: {xtype: 'accountForm',
                    id: 'accountForm'}
        }).show();
    },

    /**
     * Handle Account Edit button
     */
    handleEdit: function(){
        var record = this.getAccountsGrid().getSelectionModel().getSelection()[0];
        var accountEditWindow = Ext.create('Ext.window.Window', {
            title: 'Accounts',
            closeAction: 'destroy',
            id: 'editAccountWindow',
            items: {xtype: 'accountEditForm',
                    id: 'editAccountForm'}
        });
        var accountsForm = Ext.ComponentQuery.query('#editAccountForm')[0].getForm();
        accountsForm.setValues({'account': record.get('account'),
                               'name': record.get('name'),
                               'discount_rate': record.get('discount_rate'),
                               'late_charge_rate': record.get('late_charge_rate'),
                               'utility_account_number': record.get('utility_account_number'),
                               'payee': record.get('payee'),
                               'service_type': record.get('service_type'),
                               'ba_addressee': record.get('ba_addressee'),
                               'ba_street': record.get('ba_street'),
                               'ba_city': record.get('ba_city'),
                               'ba_state': record.get('ba_state'),
                               'ba_postal_code': record.get('ba_postal_code'),
                               'sa_addressee': record.get('sa_addressee'),
                               'sa_street': record.get('sa_street'),
                               'sa_city': record.get('sa_city'),
                               'sa_state': record.get('sa_state'),
                               'sa_postal_code': record.get('sa_postal_code')
                               });
        accountEditWindow.show();
        
    },

    /**
     * Handle the filter being changed.
     */
    handleFilter: function( combo, newValue, oldValue, eOpts) {
        // We're filtering every record, so we have to use AccountsStore
        // and not AccountsMemoryStore
        // We're filtering every record, so we have to use AccountsStore
        // and not AccountsMemoryStore
        var accountsStore = this.getAccountsStore();
        var prefStore = this.getPreferencesStore();
        var allRecords = accountsStore.getRange();
        var filter = this.getAccountsFilterStore().findRecord('value', combo.getValue());
        var filterFn = filter.get('filter').filterFn;
        accountsStore.clearFilter(true);
        accountsStore.filter({filterFn: filterFn});

        if(accountsStore.count()!=0 && prefStore.count()!=0 && newValue){
            var rec= prefStore.findRecord('key', 'filtername');
            rec.set('value', newValue);
        }
    },

    /**
     * Get the next account number and add it populate the new account number field
     */
    loadNextAccountNumber: function(accountsForm) {
        var newAccountField = this.getAccountForm().down('textfield[name=account]');
        var store = this.getAccountsStore();

        newAccountField.setValue(store.getNextAccountNumber());
    },

    /**
     * Edit an existing account
     */
    saveEditChanges: function() {
        var store = this.getAccountsStore();
        var accountEditForm = this.getAccountEditForm();
        var editWindow = Ext.ComponentQuery.query('#editAccountWindow');
        if (accountEditForm.getForm().isValid()) {
            var values = accountEditForm.getValues();
            store.clearFilter();
            var record = store.findRecord('account', values.account);
            record.set(values);
            editWindow[0].close();
        }
    },

    /**
     * Save the new account.
     */
    saveNewAccount: function() {
        var accountForm = this.getAccountForm(),
            accountsGrid = this.getAccountsGrid(),
            newAccountWindow = Ext.ComponentQuery.query('#createAccountWindow'),
            makeAnotherAccount = accountForm.down('[name=makeAnotherAccount]').checked;
        var store = this.getAccountsStore();

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

                        // Test if the current filter would filter out the newly
                        // created account and if yes, set the filter to none
                        if(!filterRec.get('filter').filterFn(accountRec)){
                            var noneFilter = filterStore.findRecord('value', 'none');
                            var filterCombo = this.getAccountsFilter();
                            filterCombo.select(noneFilter);
                        }

                        store.sort({
                            property: 'account',
                            direction: 'DESC'
                        });
                        store.loadPage(1);
                        accountsGrid.getSelectionModel().select([accountRec]);
                    },
                    callback: function(){
                        store.resumeAutoSync();
                    },
                    scope: this
                });
                newAccountWindow[0].close();
            }else {
                accountForm.getForm().reset();
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
        var selected = this.getAccountsGrid().getSelectionModel().getSelection();
        this.getEditBtn().setDisabled(!(selected.length == 1));
        this.getMergeBtn().setDisabled(!(selected.length == 2));
    },
    /**
     * handle merge records button
     */
    handleMerge: function () {
        var records = this.getAccountsGrid().getSelectionModel().getSelection();
        Ext.create('ReeBill.view.accounts.MergeDialog', {
            records: records,
            basedOn: 'ReeBill.view.accounts.Accounts',
            store: this.getAccountsStore(),
            exclude: ['casualname', 'primusname', 'codename', 'lastevent',
            'service_type', 'template_account']
        }).show();
    }

});
