Ext.define('ReeBill.controller.Payments', {
    extend: 'Ext.app.Controller',

    stores: [
        'Payments'
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
                beforeedit: this.handleBeforeEdit,
                edit: this.handleEdit
            },
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
        var selectedAccount = this.getAccountsGrid().getSelectionModel().getSelection();

        if (!selectedAccount.length)
            return;

        this.getPaymentsStore().load({
            params: {
                account: selectedAccount[0].get('account')
            }
        });
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

        Ext.Ajax.request({
            url: 'http://'+'reebill-demo.skylineinnovations.net'+'/reebill/payment',
            method: 'POST',
            params: {
                xaction: 'create',
                account: selectedAccount[0].get('account'),
                service: '',
                sequence: '',
                rows: '{}'
            },
            success: function() {
                store.reload();
            }
        });
    },

    /**
     * Handle the edit of a row.
     */
    handleBeforeEdit: function(editor, e) {
        if (!e.record.get('editable'))
            return false;
    },

    /**
     * Handle the edit of a row.
     */
    handleEdit: function(editor, e) {
        var updated = e.record,
            store = this.getPaymentsStore(),
            selectedAccount = this.getAccountsGrid().getSelectionModel().getSelection();

        var updateProperties = Object.getOwnPropertyNames(updated.modified);

        if (!updated || updateProperties.length === 0)
            return;

        var updatedData = Ext.clone(updated.data);
        updatedData.date_applied = Ext.util.Format.date(updatedData.date_applied, 'Y-m-d') + 'T00:00:00';

        var params =  {
            xaction: 'update',
            account: selectedAccount[0].get('account'),
            rows: JSON.stringify(updatedData),
            sequence: '',
            service: this.getServiceForCharges().getValue() || ''
        };

        Ext.Ajax.request({
            url: 'http://'+'reebill-demo.skylineinnovations.net'+'/reebill/payment',
            method: 'POST',
            params: params,
            success: function(response, request) {
                var jsonData = Ext.JSON.decode(response.responseText);
                if (jsonData.success) {
                    store.reload();
                } else {
                    Ext.Msg.alert('Error', jsonData.errors.details);
                }
            }
        });
    },

    /**
     * Handle the delete button being clicked.
     */
    handleDelete: function() {
        var store = this.getPaymentsStore(),
            selectedAccount = this.getAccountsGrid().getSelectionModel().getSelection(),
            selectedPayment = this.getPaymentsGrid().getSelectionModel().getSelection();;

        if (!selectedAccount || !selectedAccount.length || !selectedPayment || !selectedPayment.length)
            return;

        Ext.Ajax.request({
            url: 'http://'+'reebill-demo.skylineinnovations.net'+'/reebill/payment',
            method: 'POST',
            params: {
                xaction: 'destroy',
                account: selectedAccount[0].get('account'),
                service: '',
                sequence: '',
                rows: selectedPayment[0].get('id')
            },
            success: function() {
                store.reload();
            }
        });
    }    

});
