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
        selector: '[action=utilbillCompute]'
    },{
        ref: 'utilbillRemove',
        selector: '[action=utilbillRemove]'
    },{
        ref: 'utilbillToggleProcessed',
        selector: '[action=utilbillToggleProcessed]'
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
            '[action=resetUploadUtilityBillForm]': {
                click: this.handleReset
            },
            '[action=submitUploadUtilityBillForm]': {
                click: this.handleSubmit
            },
            '[action=utilbillCompute]': {
                click: this.handleCompute
            },
            '[action=utilbillRemove]': {
                click: this.handleDelete
            },
            '[action=utilbillToggleProcessed]': {
                click: this.handleToggleProcessed
            }
        });

        this.getUtilityBillsStore().on({
            beforeload: function(store){
                var grid = this.getUtilityBillsGrid();
                grid.setLoading(true);
            },
            load: function(store) {
                var grid = this.getUtilityBillsGrid();
                grid.setLoading(false);
                this.initalizeUploadForm();
            },
            scope: this
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

        store.getProxy().setExtraParam('account', selected[0].get('account'));
        store.reload();
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
        var store = this.getUtilityBillsStore();

        form.getForm().reset();

        if (!selected || !selected.length)
            return;
        var lastEndDate = store.getLastEndDate();
        // If there is no record in the store set the date to one month ago from today
        if(!lastEndDate){
            lastEndDate = Ext.Date.add(new Date(), Ext.Date.MONTH, -1);
        }
        accountField.setValue(selected[0].get('account'));
        startDateField.setValue(lastEndDate);
        endDateField.setValue(Ext.Date.add(lastEndDate, Ext.Date.MONTH, 1));
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
            selected = this.getUtilityBillsGrid().getSelectionModel().getSelection()[0];

        if (!selected)
            return;

        selected.set('action', 'compute');
    },

    /**
     * Handle the compute button being clicked.
     */
    handleDelete: function() {
        var scope = this,
            store = this.getUtilityBillsStore(),
            grid = this.getUtilityBillsGrid(),
            selected = this.getUtilityBillsGrid().getSelectionModel().getSelection()[0];

        if (!selected)
            return;

        Ext.Msg.confirm('Confirm deletion',
            'Are you sure you want to delete the selected Utility Bill(s)?',
            function(answer) {
                if (answer == 'yes') {
                    store.remove(selected)
                    grid.fireEvent('deselect', selected, 0);
                }
            });
    },
    
    /**
     * Handle the toggle processed button being clicked.
     */
    handleToggleProcessed: function() {
        var grid = this.getUtilityBillsGrid(),
            selected = grid.getSelectionModel().getSelection()[0];

        if (!selected)
            return;

        selected.set('processed', !selected.get('processed'));
    }

});
