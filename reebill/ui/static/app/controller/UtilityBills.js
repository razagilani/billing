Ext.define('ReeBill.controller.UtilityBills', {
    extend: 'Ext.app.Controller',

    stores: [
        'UtilityBills', 'ReeBillVersions'
    ],
    
    refs: [{
        ref: 'uploadUtilityBillForm',
        selector: 'uploadUtilityBill'
    },{
        ref: 'accountsGrid',
        selector: 'grid[id=accountsGrid]'
    },{
        ref: 'utilityBillsGrid',
        selector: 'grid[id=utilityBillsGrid]'
    },{
        ref: 'utilbillCompute',
        selector: 'button[action=utilbillCompute]'
    },{
        ref: 'utilbillRemove',
        selector: 'button[action=utilbillRemove]'
    },{
        ref: 'utilbillToggleProcessed',
        selector: 'button[action=utilbillToggleProcessed]'
    }],    
    
    init: function() {
        this.application.on({
            scope: this
        });
        
        this.control({
            'grid[id=utilityBillsGrid]': {
                selectionchange: this.handleRowSelect
            },
            'panel[name=utilityBillsTab]': {
                activate: this.handleActivate
            },
            'button[action=resetUploadUtilityBillForm]': {
                click: this.handleReset
            },
            'button[action=submitUploadUtilityBillForm]': {
                click: this.handleSubmit
            },
            'button[action=utilbillCompute]': {
                click: this.handleCompute
            },
            'button[action=utilbillRemove]': {
                click: this.handleDelete
            },
            'button[action=utilbillToggleProcessed]': {
                click: this.handleToggleProcessed
            }
        });

    },

    /**
     * Handle the row selection.
     */
    handleRowSelect: function(combo, recs) {
        var hasSelections = recs.length > 0;

        this.getUtilbillCompute().setDisabled(!hasSelections);
        this.getUtilbillToggleProcessed().setDisabled(!hasSelections);

        var hasReebill = false;
        Ext.each(recs, function(rec) {
            if (rec.get('reebills').length > 0)
                hasReebill = true;
        });

        this.getUtilbillRemove().setDisabled(!hasSelections || hasReebill);
    },

    /**
     * Handle the panel being activated.
     */
    handleActivate: function() {
        var selected = this.getAccountsGrid().getSelectionModel().getSelection();
        var store = this.getUtilityBillsStore();

        if (!selected || !selected.length)
            return;

        this.initalizeUploadForm();

        store.getProxy().setExtraParam('account', selected[0].get('account'));
        store.loadPage(1);
    },

    /**
     * Initialize the upload form.
     */
    initalizeUploadForm: function() {
        var form = this.getUploadUtilityBillForm(),
            selected = this.getAccountsGrid().getSelectionModel().getSelection(),
            accountField = form.down('[name=account]'),
            startDateField = form.down('[name=begin_date]'),
            endDateField = form.down('[name=end_date]');

        form.getForm().reset();

        if (!selected || !selected.length)
            return;

        accountField.setValue(selected[0].get('account'));

        Ext.Ajax.request({
            url: 'http://'+window.location.host+'/reebill/utilitybills/last_end_date',
            method: 'GET',
            params: { 
                account: selected[0].get('account')
            },
            success: function(response){
                var jsonData = Ext.JSON.decode(response.responseText);
                var dt = new Date(jsonData['date'])
                startDateField.setValue(dt);
                endDateField.setValue(Ext.Date.add(dt, Ext.Date.MONTH, 1));
            }
        });
    },

    /**
     * Handle the compute button being clicked.
     */
    handleReset: function() {
        this.initalizeUploadForm(); 
    },

    /**
     * Handle the submit button being clicked.
     */
    handleSubmit: function() {
        var scope = this,
            store = this.getUtilityBillsStore();

        this.getUploadUtilityBillForm().getForm().submit({
            url: 'http://'+window.location.host+'/reebill/utilitybills',
            success: function() {
                scope.initalizeUploadForm();
                store.reload();
            },
            failure: function(form, action) {
                Ext.Msg.alert('Error', 'Error uploading utility bill.')
            }
        }); 
    },

    /**
     * Handle the compute button being clicked.
     */
    handleCompute: function() {
        var scope = this,
            selected = this.getUtilityBillsGrid().getSelectionModel().getSelection();

        if (!selected || !selected.length)
            return;

        Ext.Ajax.request({
            url: 'http://'+window.location.host+'/rest/compute_utility_bill',
            params: { 
                utilbill_id: selected[0].get('id')
            },
            success: function(response, request) {
                var jsonData = Ext.JSON.decode(response.responseText);
                if (jsonData.success) {
                    scope.getUtilityBillsStore().reload();
                }
            },
        });
    },

    /**
     * Handle the compute button being clicked.
     */
    handleDelete: function() {
        var scope = this,
            store = this.getUtilityBillsStore(),
            selected = this.getUtilityBillsGrid().getSelectionModel().getSelection(),
            selectedAccount = this.getAccountsGrid().getSelectionModel().getSelection();

        if (!selected || !selected.length)
            return;

        Ext.Msg.confirm('Confirm deletion',
            'Are you sure you want to delete the selected Utility Bill(s)?',
            function(answer) {
                if (answer == 'yes') {
                    store.remove(selected)
                }
            });
    },
    
    /**
     * Handle the toggle processed button being clicked.
     */
    handleToggleProcessed: function() {
        var grid = this.getUtilityBillsGrid(),
            selected = grid.getSelectionModel().getSelection();

        console.log(selected);
        if (!selected || selected.length != 1)
            return;

        var rec = selected[0];
        rec.set('processed', !rec.get('processed'));
    }

});
