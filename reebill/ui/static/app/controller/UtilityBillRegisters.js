Ext.define('ReeBill.controller.UtilityBillRegisters', {
    extend: 'Ext.app.Controller',

    stores: [
        'UtilityBillRegisters'
    ],
    
    refs: [{
        ref: 'utilityBillRegistersGrid',
        selector: 'grid[id=utilityBillRegistersGrid]'
    },{
        ref: 'accountsGrid',
        selector: 'grid[id=accountsGrid]'
    },{
        ref: 'utilityBillsGrid',
        selector: 'grid[id=utilityBillsGrid]'
    },{
        ref: 'removeUtilityBillRegisterButton',
        selector: 'button[action=removeUtilityBillRegister]'
    }],    

    init: function() {
        var me = this,
            store = me.getUtilityBillRegistersStore();

        this.application.on({
            scope: this
        });
        
        this.control({
            'panel[name=metersTab]': {
                activate: this.handleActivate
            },
            'grid[id=utilityBillRegistersGrid]': {
                selectionchange: this.handleRowSelect,
            },
            'button[action=newUtilityBillRegister]': {
                click: this.handleNew
            },
            'button[action=removeUtilityBillRegister]': {
                click: this.handleDelete
            },
        });

    },

    /**
     * Handle the panel being activated.
     */
    handleActivate: function() {
        var selectedBill = this.getUtilityBillsGrid().getSelectionModel().getSelection();
        var store = this.getUtilityBillRegistersStore();

        if (!selectedBill.length)
            return;

        var params = {
            utilbill_id: selectedBill[0].get('id')
        }

        store.getProxy().extraParams = params;
        store.load();
    },

    /**
     * Handle the row selection.
     */
    handleRowSelect: function() {
        var hasSelections = this.getUtilityBillsGrid().getSelectionModel().getSelection().length > 0;

        this.getRemoveUtilityBillRegisterButton().setDisabled(!hasSelections);
        this.getUploadIntervalMeterForm().setDisabled(!hasSelections);
    },

    /**
     * Handle the new utitlity bill button being clicked.
     */
    handleNew: function() {
        var store = this.getUtilityBillRegistersStore(),
            selectedAccount = this.getAccountsGrid().getSelectionModel().getSelection(),
            selectedBill = this.getUtilityBillsGrid().getSelectionModel().getSelection();

        if (!selectedAccount || !selectedAccount.length || !selectedBill || !selectedBill.length)
            return;

        store.add({identifier:'new Register',
                   meter_identifier:'new Meter'})

    },

    /**
     * Handle the delete utitlity bill button being clicked.
     */
    handleDelete: function() {
        var store = this.getUtilityBillRegistersStore(),
            selectedAccount = this.getAccountsGrid().getSelectionModel().getSelection(),
            selectedBill = this.getUtilityBillsGrid().getSelectionModel().getSelection(),
            selectedUtilityBillRegister = this.getUtilityBillRegistersGrid().getSelectionModel().getSelection();

        if (!selectedAccount || !selectedAccount.length || !selectedBill || !selectedBill.length
                || !selectedUtilityBillRegister || !selectedUtilityBillRegister.length)
            return;

        store.remove(selectedUtilityBillRegister);
    },


});
