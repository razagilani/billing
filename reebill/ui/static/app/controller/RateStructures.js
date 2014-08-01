Ext.define('ReeBill.controller.RateStructures', {
    extend: 'Ext.app.Controller',

    stores: [
        'RateStructures'
    ],
    
    views:[
        'RateStructures'
    ],

    refs: [{
        ref: 'rateStructuresGrid',
        selector: 'grid[id=rateStructuresGrid]'
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
        ref: 'removeRateStructure',
        selector: 'button[action=removeRateStructure]'
    },{
        ref: 'formulaField',
        selector: 'formulaField'
    },{
        ref: 'groupTextField',
        selector: 'groupTextField'
    }],

    init: function() {
        this.application.on({
            scope: this
        });
        
        this.control({
            'grid[id=rateStructuresGrid]': {
                selectionchange: this.handleRowSelect,
                cellclick: this.handleCellClick
            },
            '#rateStructureGridView': {
                refresh: this.updateGroupTextField
            },
            'panel[name=rateStructuresTab]': {
                activate: this.handleActivate
            },
            'button[action=newRateStructure]': {
                click: this.handleNew
            },
            'button[action=removeRateStructure]': {
                click: this.handleDelete
            },
            'button[action=regenerateRateStructure]': {
                click: this.handleRegenerate
            },
            'formulaField':{
                specialkey: this.handleFormulaFieldEnter
            },
            'groupTextField':{
                specialkey: this.handleGroupTextFieldEnter
            }
        });

    },

    /**
     * Handle the panel being activated.
     */
    handleActivate: function() {
        var store = this.getRateStructuresStore();
        var selectedBill = this.getUtilityBillsGrid().getSelectionModel().getSelection();
        var field = this.getFormulaField();
        var groupTextField = this.getGroupTextField();

        if (!selectedBill.length)
            return;

        var params = {
            utilbill_id: selectedBill[0].get('id')
        }
        store.getProxy().extraParams = params;
        store.load();

        field.setDisabled(true);
        groupTextField.setDisabled(true);
    },

    /**
     * Handle the panel being activated.
     */
    handleCellClick: function(grid, td, cellIndex, record, tr, rowIndex, e, eOpts) {
        var field = this.getFormulaField();
        var grid = this.getRateStructuresGrid();
        var dataIndex = grid.getView().getHeaderCt().getHeaderAtIndex(cellIndex).dataIndex;

        var formulaIndex = record.getFormulaKey(dataIndex);
        field.setDisabled(formulaIndex === null);
        field.setValue(record.get(formulaIndex));

        field.lastRecord = record;
        field.lastDataIndex = dataIndex;
    },

    /**
     * Handle a special key press in the Formula Field
     */
    handleFormulaFieldEnter: function(f, e, eOpts) {
        var field = this.getFormulaField();
        var record = field.lastRecord;
        var dataIndex = field.lastDataIndex;
        var formulaIndex = record.getFormulaKey(dataIndex);

        if (e.getKey() == e.ENTER) {
            record.set(formulaIndex, field.getValue());
        }
        console.log(record, formulaIndex, field.getValue());
    },

    /**
     * Handle a special key press in the GroupTextField
     */
    handleGroupTextFieldEnter: function(f, e, eOpts) {
        var field = this.getGroupTextField();
        var selected = this.getRateStructuresGrid().getSelectionModel().getSelection()[0];

        if (e.getKey() == e.ENTER) {
            selected.set('group', field.getValue());
        }
    },

    /**
     * Handle the row selection.
     */
    handleRowSelect: function() {
        var hasSelections = this.getUtilityBillsGrid().getSelectionModel().getSelection().length > 0;
        var selected = this.getRateStructuresGrid().getSelectionModel().getSelection()[0];
        this.getRemoveRateStructure().setDisabled(!hasSelections);

        // Set group in GroupTextField
        if(hasSelections && selected !== undefined){
            this.updateGroupTextField();
        }
     },

    /**
     * Update the GroupTextField
     */
    updateGroupTextField: function(){
        var hasSelections = this.getUtilityBillsGrid().getSelectionModel().getSelection().length > 0;
        var selected = this.getRateStructuresGrid().getSelectionModel().getSelection()[0];

        if(hasSelections && selected !== undefined){
            var groupTextField = this.getGroupTextField();
            groupTextField.setDisabled(false);
            groupTextField.setValue(selected.get('group'));
        }
    },

    /**
     * Handle the new button being clicked.
     */
    handleNew: function() {
        var store = this.getRateStructuresStore(),
            selectedBill = this.getUtilityBillsGrid().getSelectionModel().getSelection();

        if (!selectedBill || !selectedBill.length)
            return;

        store.add({'name': 'New RSI'});
    },

    /**
     * Handle the delete button being clicked.
     */
    handleDelete: function() {
        var store = this.getRateStructuresStore();
        var selected = this.getRateStructuresGrid().getSelectionModel().getSelection()[0];

        if (!selected)
            return;

        store.remove(selected);
    },

    /**
     * Handle the regenerate button being clicked.
     */
    handleRegenerate: function() {
        var store = this.getRateStructuresStore(),
            selectedBill = this.getUtilityBillsGrid().getSelectionModel().getSelection();

        if (!selectedBill || !selectedBill.length)
            return;

        Ext.Ajax.request({
            url: 'http://'+window.location.host+'/rest/regenerate_rs',
            params: {
                utilbill_id: selectedBill[0].get('id')
            },
            success: function(response) {
                var jsonData = Ext.JSON.decode(response.responseText);
                if (jsonData.success) {
                    store.reload();
                }
            },
        });
    }
});
