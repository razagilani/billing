Ext.define('ReeBill.controller.Accounts', {
    extend: 'Ext.app.Controller',

    stores: [
        'Accounts'
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
    },

    /**
     * Handle the panel being activated.
     */
    handleActivate: function() {
        // Add the configurable default sort the first time through.
        if (!this.getAccountsStore().sorters.length) {
            this.getAccountsStore().sorters.add({
                property: config.defaultAccountSortField,
                direction: config.defaultAccountSortDir
            });
        }

        if (!this.getAccountsStore().getCount())
            this.getAccountsStore().load();
    },

    /**
     * Handle the filter being changed.
     */
    handleFilter: function() {
        var filter = this.getAccountsFilter().getValue();

        this.getAccountsStore().load({
            params: {
                filtername: filter
            }
        });
    },

    /**
     * Get the next account number and add it populate the new account numnber field
     */
    loadNextAccountNumber: function() {
        var newAccountField = this.getAccountForm().down('textfield[name=account]');

        Ext.Ajax.request({
            url: 'http://' + 'reebill-demo.skylineinnovations.net' + '/reebill/get_next_account_number',
            success: function(response){
                var jsonData = Ext.JSON.decode(response.responseText);
                newAccountField.setValue(jsonData['account']);
            }
        });
    },

    /**
     * Save the new account.
     */
    saveNewAccount: function() {
        var accountForm = this.getAccountForm(),
            accountsGrid = this.getAccountsGrid(),
            makeAnotherAccount = accountForm.down('[name=makeAnotherAccount]');

        if (accountForm.getForm().isValid()) {
            var values = accountForm.getForm().getValues();

            accountForm.getForm().submit({
                url: 'http://' + 'reebill-demo.skylineinnovations.net' + '/reebill/new_account',
                success: function(form, action) {
                    Ext.Msg.alert('Success', 'New account created.');

                    accountForm.getForm().reset();
                    accountsGrid.getStore().reload();

                    if (!makeAnotherAccount.getValue())
                        accountsGrid.expand();
                    else
                        this.loadNextAccountNumber();
                },
                failure: function() {
                    Ext.Msg.alert('FAILURE', 'New account not created.');
                }
            });
        }
    },

    /**
     * Handle the account selection.
     */
    handleAccountSelect: function() {

    }

});
