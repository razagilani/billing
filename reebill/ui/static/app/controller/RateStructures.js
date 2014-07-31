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
    }],

    init: function() {
        this.application.on({
            scope: this
        });
        
        this.control({
            'grid[id=rateStructuresGrid]': {
                selectionchange: this.handleRowSelect,
                edit: this.handleEdit,
                cellclick: this.handleCellClick
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

        if (!selectedBill.length)
            return;

        var params = {
            utilbill_id: selectedBill[0].get('id')
        }
        store.getProxy().extraParams = params;
        store.load();

        field.setDisabled(true);
    },

    /**
     * Handle the panel being activated.
     */
    handleCellClick: function(grid, td, cellIndex, record, tr, rowIndex, e, eOpts) {
        var field = this.getFormulaField();
        var grid = this.getRateStructuresGrid();
        var dataIndex = grid.getView().getHeaderCt().getHeaderAtIndex(cellIndex).dataIndex;

        var formulaIndex = record.getFormulaKey(dataIndex);
        field.setValue(record.get(formulaIndex));
        field.setDisabled(false);

        field.lastRecord = record;
        field.lastDataIndex = dataIndex;
    },

    /**
     * Handle the row selection.
     */
    handleRowSelect: function() {
        var hasSelections = this.getUtilityBillsGrid().getSelectionModel().getSelection().length > 0;

        this.getRemoveRateStructure().setDisabled(!hasSelections);
     },

    /**
     * Handle the new button being clicked.
     */
    handleNew: function() {
        var store = this.getRateStructuresStore(),
            selectedBill = this.getUtilityBillsGrid().getSelectionModel().getSelection();

        if (!selectedBill || !selectedBill.length)
            return;

        Ext.Ajax.request({
            url: 'http://'+window.location.host+'/rest/rsi',
            method: 'POST',
            params: {
                xaction: 'create',
                utilbill_id: selectedBill[0].get('id'),
                rows: '[{}]'
            },
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
     * Handle the edit of a row.
     */
    handleEdit: function(editor, e) {
        var updated = e.record,
            store = this.getRateStructuresStore(),
            selectedBill = this.getUtilityBillsGrid().getSelectionModel().getSelection();

        var updateProperties = Object.getOwnPropertyNames(updated.modified);

        if (!updated || updateProperties.length === 0)
            return;

        var params =  {
            xaction: 'update',
            utilbill_id: selectedBill[0].get('id'),
            rows: JSON.stringify(updated.data)
        };

        Ext.Ajax.request({
            url: 'http://'+window.location.host+'/rest/rsi',
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
        var store = this.getRateStructuresStore(),
            selectedAccount = this.getAccountsGrid().getSelectionModel().getSelection(),
            selectedBill = this.getUtilityBillsGrid().getSelectionModel().getSelection(),
            selectedRateStructure = this.getRateStructuresGrid().getSelectionModel().getSelection(),
            selectedReebill = this.getReebillsGrid().getSelectionModel().getSelection(),
            service = this.getServiceForCharges().getValue() || '';

        if (!selectedAccount || !selectedAccount.length || !selectedBill || !selectedBill.length 
                || !selectedRateStructure || !selectedRateStructure.length)
            return;

        Ext.Ajax.request({
            url: 'http://'+window.location.host+'/rest/rsi',
            method: 'POST',
            params: {
                xaction: 'destroy',
                service: service,
                sequence: selectedReebill.length ? selectedReebill[0].get('sequence') || '' : '',
                account: selectedAccount[0].get('account'),
                utilbill_id: selectedBill[0].get('id'),
                rows: '["' + selectedRateStructure[0].get('id') + '"]'
            },
            success: function() {
                store.reload();
            }
        });
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
