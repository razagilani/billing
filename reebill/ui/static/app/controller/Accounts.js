Ext.define('ReeBill.controller.Accounts', {
    extend: 'Ext.app.Controller',

    stores: [
        'Accounts', 'AccountsMemory', 'AccountsFilter'
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
            add: function(){
                var accountForm = this.getAccountForm();
                accountForm.getForm().reset();
            },
            scope: this
        });
    },

    /**
     * Handle the panel being activated.
     */
    handleActivate: function() {
        var filter = this.getAccountsFilterStore().getAt(0);
        var filterCombo = this.getAccountsFilter();
        filterCombo.select(filter);
    },

    /**
     * Handle the filter being changed.
     */
    handleFilter: function() {
        // We're filtering every record, so we have to use AccountsStore
        // and not AccountsMemoryStore
        var store = this.getAccountsMemoryStore()
        var allRecords = this.getAccountsStore().getRange();
        var filter = this.getAccountsFilter().getValue();
        var filteredRecords = Ext.Array.filter(allRecords, filter.filterFn)

        store.getProxy().data = filteredRecords;
        store.loadPage(1);
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
