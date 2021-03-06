Ext.define('ReeBill.controller.Charges', {
    extend: 'Ext.app.Controller',

    stores: [
        'Charges', 'UtilityBills', 'PreviousCharges'
    ],
    
    views:[
        'charges.Charges'
    ],

    refs: [{
        ref: 'chargesGrid',
        selector: 'grid[id=chargesGrid]'
    },{
        ref: 'accountsGrid',
        selector: 'grid[id=accountsGrid]'
    },{
        ref: 'reebillsGrid',
        selector: 'grid[id=reebillsGrid]'
    },{
        ref: 'utilityBillsGrid',
        selector: 'grid[id=utilityBillsGrid]'
    },{
        ref: 'removeCharge',
        selector: '[action=removeCharge]'
    },{
        ref: 'regenerateCharge',
        selector: '[action=regenerateCharge]'
    },{
        ref: 'newCharge',
        selector: '[action=newCharge]'
    },{
        ref: 'recomputeCharges',
        selector: '[action=recomputeCharges]'
    },{
        ref: 'formulaField',
        selector: 'formulaField'
    }],

    init: function() {
        this.application.on({
            scope: this
        });
        
        this.control({
            'grid[id=chargesGrid]': {
                selectionchange: this.handleRowSelect
            },
            '#chargesGridView': {
                refresh: this.updateTextFields
            },
            'panel[name=chargesTab]': {
                activate: this.handleActivate
            },
            '[action=newCharge]': {
                click: this.handleNew
            },
            '[action=removeCharge]': {
                click: this.handleDelete
            },
            '[action=regenerateCharge]': {
                click: this.handleRegenerate
            },
            '[action=recomputeCharges]': {
                click: this.handleRecompute
            },
            'formulaField':{
                specialkey: this.handleFormulaFieldEnter
            }
        });

        this.getChargesStore().on({
            write: this.handleRowSelect,
            scope: this
        });
    },

    /**
     * Handle the panel being activated.
     */
    handleActivate: function() {
        var store = this.getChargesStore();
        var selectedBill = this.getUtilityBillsGrid().getSelectionModel().getSelection()[0];
        var processed = selectedBill.get('processed');
        this.getRemoveCharge().setDisabled(processed);
        this.getNewCharge().setDisabled(processed);
        this.getRegenerateCharge().setDisabled(processed);
        this.getRecomputeCharges().setDisabled(processed);
        if (!selectedBill)
            return;

        store.getProxy().extraParams = {
            utilbill_id: selectedBill.get('id')
        };
        store.reload();

        this.getChargesGrid().getSelectionModel().deselectAll();
        this.updateTextFields();

        // Previous Bill
        var utilbillStore = this.getUtilityBillsStore();
        var previousBillIndex = utilbillStore.indexOf(selectedBill) + 1;
        var previousBill = utilbillStore.getAt(previousBillIndex);
        var prevStore = this.getPreviousChargesStore();
        if(previousBill){
            prevStore.getProxy().extraParams = {
                utilbill_id: previousBill.get('id')
            };
            prevStore.reload();
        }else{
            prevStore.loadData([]);
        }
    },

    /**
     * Handle a special key press in the Formula Field
     */
    handleFormulaFieldEnter: function(f, e) {
        if (e.getKey() == e.ENTER) {
            var field = this.getFormulaField();
            var selected = this.getChargesGrid().getSelectionModel().getSelection()[0];
            selected.set('quantity_formula', field.getValue());
            this.getChargesGrid().focus();
        }
    },

    /**
     * Handle the row selection.
     */
    handleRowSelect: function() {
        var selectedAccount = this.getUtilityBillsGrid().getSelectionModel().getSelection()[0];
        var hasSelections = this.getUtilityBillsGrid().getSelectionModel().getSelection().length > 0;
        var processed = selectedAccount.get('processed');
        this.getRemoveCharge().setDisabled(!hasSelections || processed);
        this.updateTextFields();
        this.getChargesGrid().focus();
     },

    /**
     * Update the textFields
     */
    updateTextFields: function(){
        var hasSelections = this.getUtilityBillsGrid().getSelectionModel().getSelection().length > 0;
        var selected = this.getChargesGrid().getSelectionModel().getSelection()[0];

        var formulaField = this.getFormulaField();

        if(hasSelections && selected !== undefined){
            formulaField.setDisabled(false);
            formulaField.setValue(selected.get('quantity_formula'));
        }else{
            formulaField.setDisabled(true);
            formulaField.setValue('');
        }
    },

    /**
     * Handle the new button being clicked.
     */
    handleNew: function() {
        var store = this.getChargesStore(),
            selectedBill = this.getUtilityBillsGrid().getSelectionModel().getSelection();

        if (!selectedBill || !selectedBill.length)
            return;

        store.suspendAutoSync();
        store.add({
            rsi_binding: 'New RSI',
            description: 'Enter Description',
            rate: 0,
            unit: 'dollars',
            type: 'supply',
            utilbill_id: selectedBill[0].internalId
        });
        store.sync({success:function(batch){
            var record = batch.operations[0].records[0];
            var plugin = this.getChargesGrid().findPlugin('cellediting');
            plugin.startEdit(record, 2);
        }, scope: this});
        store.resumeAutoSync();
        this.updateTextFields();
    },

    /**
     * Handle the delete button being clicked.
     */
    handleDelete: function() {
        var store = this.getChargesStore();
        var selected = this.getChargesGrid().getSelectionModel().getSelection()[0];

        if (!selected)
            return;

        store.remove(selected);
        this.updateTextFields();
        store.reload();
    },

    /**
     * Handle the regenerate button being clicked.
     */
    handleRegenerate: function() {
        this.sendAction('regenerate_charges');
    },

    /**
     * Handle the recompute button being clicked.
     */
    handleRecompute: function() {
        this.sendAction('compute');
    },

    sendAction: function(action, callback , scope){
        var grid = this.getChargesGrid();
        var store = this.getUtilityBillsStore();
        var selectedBill = this.getUtilityBillsGrid().getSelectionModel().getSelection()[0];

        grid.setLoading(true);
        store.suspendAutoSync();
        selectedBill.set('action', action);
        store.sync({
            success:function(batch) {
                this.getChargesStore().reload({
                    callback: function(){
                        grid.setLoading(false);
                    },
                    scope:this
                });
            },
            failure: function(){
                grid.setLoading(false);
            },
            scope: this
        });
        store.resumeAutoSync();
        this.updateTextFields();

        if(callback)
            callback.call(scope);
    }
});
