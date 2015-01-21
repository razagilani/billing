Ext.define('ReeBill.controller.Payments', {
    extend: 'Ext.app.Controller',

    stores: [
        'Payments'
    ],

    views: [
        'payments.Payments', 'accounts.Accounts'
    ],
    
    refs: [{
        ref: 'accountsGrid',
        selector: 'grid[id=accountsGrid]'
    },{
        ref: 'paymentsGrid',
        selector: 'grid[id=paymentsGrid]'
    },{
        ref: 'deletePaymentButton',
        selector: 'button[action=deletePayment]'
    },{
        ref: 'serviceForCharges',
        selector: 'combo[name=serviceForCharges]'
    }],    

    init: function() {
        this.application.on({
            scope: this
        });
        
        this.control({
            'grid[id=paymentsGrid]': {
                activate: this.handleActivate,
                selectionchange: this.handleRowSelect,
                beforeedit: this.handleBeforeEdit            },
            'button[action=newPayment]': {
                click: this.handleNew
            },
            'button[action=deletePayment]': {
                click: this.handleDelete
            }
        });
    },

    /**
     * Handle the panel being activated.
     */
    handleActivate: function() {
        var selectedAccount = this.getAccountsGrid().getSelectionModel().getSelection(),
            store = this.getPaymentsStore();

        if (!selectedAccount.length)
            return;

        store.getProxy().setExtraParam('account', selectedAccount[0].get('account'));
        store.loadPage(1);
    },

    /**
     * Handle the row selection.
     */
    handleRowSelect: function() {
        var selections = this.getPaymentsGrid().getSelectionModel().getSelection();

        this.getDeletePaymentButton().setDisabled(!selections.length || !selections[0].get('editable'));
     },

    /**
     * Handle the new button being clicked.
     */
    handleNew: function() {
        var store = this.getPaymentsStore(),
            selectedAccount = this.getAccountsGrid().getSelectionModel().getSelection();

        if (!selectedAccount || !selectedAccount.length)
            return;

        store.add({'date_received': new Date(), 'editable': true});
    },

    /**
     * Handle the edit of a row.
     */
    handleBeforeEdit: function(editor, e) {
        if (!e.record.get('editable'))
            return false;
    },

    /**
     * Handle the delete button being clicked.
     */
    handleDelete: function() {
        var store = this.getPaymentsStore(),
            selectedAccount = this.getAccountsGrid().getSelectionModel().getSelection(),
            selectedPayment = this.getPaymentsGrid().getSelectionModel().getSelection()[0];

        if (!selectedAccount || !selectedAccount.length || !selectedPayment)
            return;

        Ext.Msg.confirm('Confirm deletion',
            'Are you sure you want to delete the selected Payment(s)?',
            function(answer) {
                if (answer == 'yes') {
                    store.remove(selectedPayment);
                }
            });
    }    

});
