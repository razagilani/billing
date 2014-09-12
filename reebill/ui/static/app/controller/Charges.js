Ext.define('ReeBill.controller.Charges', {
    extend: 'Ext.app.Controller',

    stores: [
        'Charges', 'UtilityBills'
    ],
    
    views:[
        'Charges'
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
        ref: 'serviceForCharges',
        selector: 'combo[name=serviceForCharges]'
    },{
        ref: 'removeCharge',
        selector: 'button[action=removeCharge]'
    },{
        ref: 'formulaField',
        selector: 'formulaField'
    },{
        ref: 'groupTextField',
        selector: 'groupTextField'
    },{
        ref: 'roundRuleField',
        selector: 'roundRuleTextField'
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
            'button[action=newCharge]': {
                click: this.handleNew
            },
            'button[action=removeCharge]': {
                click: this.handleDelete
            },
            'button[action=regenerateCharge]': {
                click: this.handleRegenerate
            },
            'formulaField':{
                specialkey: this.handleFormulaFieldEnter
            },
            'groupTextField':{
                specialkey: this.handleGroupTextFieldEnter
            },
            'roundRuleTextField':{
                specialkey: this.handleRoundRuleFieldEnter
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
        var field = this.getFormulaField();
        var groupTextField = this.getGroupTextField();
        var roundRuleField = this.getRoundRuleField();

        if (!selectedBill)
            return;

        store.getProxy().extraParams = {
            utilbill_id: selectedBill.get('id')
        };
        store.reload();

        // Disable Text Fields on Activate
        field.setDisabled(true);
        groupTextField.setDisabled(true);
        roundRuleField.setDisabled(true);
    },

    /**
     * Handle a special key press in the Formula Field
     */
    handleFormulaFieldEnter: function(f, e) {
        if (e.getKey() == e.ENTER) {
            var field = this.getFormulaField()
            var selected = this.getChargesGrid().getSelectionModel().getSelection()[0];
            selected.set('quantity_formula', field.getValue());
            this.getChargesGrid().focus();
        }
    },

    /**
     * Handle a special key press in the GroupTextField
     */
    handleGroupTextFieldEnter: function(f, e) {
        var field = this.getGroupTextField();
        var selected = this.getChargesGrid().getSelectionModel().getSelection()[0];

        if (e.getKey() == e.ENTER) {
            selected.set('group', field.getValue());
            this.getChargesGrid().focus();
        }
    },

    /**
     * Handle a special key press in the GroupTextField
     */
    handleRoundRuleFieldEnter: function(f, e) {
        var field = this.getRoundRuleField();
        var selected = this.getChargesGrid().getSelectionModel().getSelection()[0];

        if (e.getKey() == e.ENTER) {
            selected.set('roundrule', field.getValue());
            this.getChargesGrid().focus();
        }
    },

    /**
     * Handle the row selection.
     */
    handleRowSelect: function() {
        var hasSelections = this.getUtilityBillsGrid().getSelectionModel().getSelection().length > 0;
        var selected = this.getChargesGrid().getSelectionModel().getSelection()[0];
        this.getRemoveCharge().setDisabled(!hasSelections);

        // Set group in GroupTextField
        if(hasSelections && selected !== undefined){
            this.updateTextFields();
        }

        var field = this.getFormulaField();
        field.setDisabled(false);
        field.setValue(selected.get('quantity_formula'));
     },



    /**
     * Update the GroupTextField & RoundRuleTextField
     */
    updateTextFields: function(){
        var hasSelections = this.getUtilityBillsGrid().getSelectionModel().getSelection().length > 0;
        var selected = this.getChargesGrid().getSelectionModel().getSelection()[0];

        if(hasSelections && selected !== undefined){
            var groupTextField = this.getGroupTextField();
            var roundRuleField = this.getRoundRuleField();

            groupTextField.setDisabled(false);
            groupTextField.setValue(selected.get('group'));

            roundRuleField.setDisabled(false);
            roundRuleField.setValue(selected.get('roundrule'));
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

        store.add({'name': 'New RSI'});
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
    },

    /**
     * Handle the regenerate button being clicked.
     */
    handleRegenerate: function() {
        var store = this.getChargesStore(),
            selectedBill = this.getUtilityBillsGrid().getSelectionModel().getSelection()[0];

        if (!selectedBill)
            return;

        selectedBill.set('action', 'regenerate_charges');
    }
});
