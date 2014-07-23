Ext.define('ReeBill.controller.Charges', {
    extend: 'Ext.app.Controller',

    stores: [
        'Charges'
    ],
    
    refs: [{
        ref: 'chargesGrid',
        selector: 'grid[id=chargesGrid]'
    },{
        ref: 'accountsGrid',
        selector: 'grid[id=accountsGrid]'
    },{
        ref: 'utilityBillsGrid',
        selector: 'grid[id=utilityBillsGrid]'
    },{
        ref: 'utilityBillVersions',
        selector: 'utilityBillVersions'
    },{
        ref: 'newChargeButton',
        selector: 'button[action=newCharge]'
    },{
        ref: 'deleteChargeButton',
        selector: 'button[action=deleteCharge]'
    },{
        ref: 'serviceForCharges',
        selector: 'combo[name=serviceForCharges]'
    }],    

    init: function() {
        this.application.on({
            scope: this
        });
        
        this.control({
            'panel[name=chargesTab]': {
                activate: this.handleActivate
            },
            'grid[id=chargesGrid]': {
                selectionchange: this.handleRowSelect,
                edit: this.handleEdit
            },
            'utilityBillVersions': {
                select: this.syncVersions
            },
            'button[action=newCharge]': {
                click: this.handleNew
            },
            'button[action=deleteCharge]': {
                click: this.handleDelete
            },
            'button[action=recalculateAll]': {
                click: this.recalculateAll
            },
            'button[action=addChargeGroup]': {
                click: this.addChargeGroup
            },
            'button[action=regenerateFromRateStructure]': {
                click: this.regenerateFromRateStructure
            }
        });
    },

    /**
     * Handle the panel being activated.
     */
    handleActivate: function() {
        var selectedBill = this.getUtilityBillsGrid().getSelectionModel().getSelection();
        var selectedVersion = this.getUtilityBillVersions().getValue();

        if (!selectedBill.length)
            return;

        var params = {
            account: selectedBill[0].get('account'),
            service: selectedBill[0].get('service'),
            utilbill_id: selectedBill[0].get('id')
        }

        if (selectedVersion !== '') {
            var versionRec = this.getUtilityBillVersions().findRecordByValue(selectedVersion);
            params.reebill_sequence = versionRec.get('sequence');
            params.reebill_version = versionRec.get('version');
        }

        this.getChargesStore().load({
            params: params
        });
    },

    /**
     * Handle the row selection.
     */
    handleRowSelect: function() {
        var hasSelections = this.getChargesGrid().getSelectionModel().getSelection().length > 0;

        this.getNewChargeButton().setDisabled(!hasSelections);
        this.getDeleteChargeButton().setDisabled(!hasSelections);
    },

    /**
     * Keep the version number in sync. There are multiple instances.
     */ 
    syncVersions: function(combo) {
        var val = combo.getValue();

        Ext.each(Ext.ComponentQuery.query('utilityBillVersions'), function(version) {
            version.setValue(val);
        });

        this.handleActivate();
    },

    /**
     * Handle the new button being clicked.
     */
    handleNew: function() {
        var store = this.getChargesStore(),
            selectedBill = this.getUtilityBillsGrid().getSelectionModel().getSelection(),
            selectedCharge = this.getChargesGrid().getSelectionModel().getSelection();

        if (!selectedBill || !selectedBill.length || !selectedCharge || !selectedCharge.length)
            return;

        Ext.Ajax.request({
            url: 'http://'+window.location.host+'/rest/actualCharges',
            method: 'POST',
            params: {
                xaction: 'create',
                utilbill_id: selectedBill[0].get('id'),
                rows: JSON.stringify([{
                    group: selectedCharge[0].get('group'),
                    rsi_binding: 'RSI binding required',
                    id: 'RSI binding required',
                    description: 'description required',
                    quantity: 0,
                    quantity_units: 'kWh',
                    rate: 0,
                    total: 0,
                }])
            },
            success: function() {
                store.reload();
            }
        });
    },

    /**
     * Handle the edit of a row.
     */
    handleEdit: function(editor, e) {
        var updated = e.record,
            store = this.getChargesStore(),
            selectedBill = this.getUtilityBillsGrid().getSelectionModel().getSelection();

        var updateProperties = Object.getOwnPropertyNames(updated.modified);

        if (!updated || updateProperties.length === 0)
            return;

        var params =  {
            utilbill_id: selectedBill[0].get('id'),
            rows: JSON.stringify([updated.data]),
            xaction: 'update'
        };

        Ext.Ajax.request({
            url: 'http://'+window.location.host+'/rest/actualCharges',
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
        var store = this.getChargesStore(),
            selectedCharge = this.getChargesGrid().getSelectionModel().getSelection(),
            selectedBill = this.getUtilityBillsGrid().getSelectionModel().getSelection();

        if (!selectedBill || !selectedBill  .length || !selectedCharge || !selectedCharge.length)
            return;

        Ext.Ajax.request({
            url: 'http://'+window.location.host+'/rest/actualCharges',
            method: 'POST',
            params: {
                xaction: 'destroy',
                utilbill_id: selectedBill[0].get('id'),
                rows: JSON.stringify([selectedCharge[0].get('id')])
            },
            success: function() {
                store.reload();
            }
        });
    },

    /**
     * Handle the recompute all button being clicked.
     */ 
    recalculateAll: function() {
        var store = this.getChargesStore(),
            selectedBill = this.getUtilityBillsGrid().getSelectionModel().getSelection();

        if (!selectedBill.length)
            return;

        Ext.Ajax.request({
            url: 'http://'+window.location.host+'/rest/compute_utility_bill',
            params: { utilbill_id: selectedBill[0].get('id') },
            success: function(result, request) {
                store.reload();
            },
        });
    },

    /**
     * Handle the add charge group  button being clicked.
     */ 
    addChargeGroup: function() {
        var store = this.getChargesStore(),
            selectedBill = this.getUtilityBillsGrid().getSelectionModel().getSelection();

        Ext.Msg.prompt('Add Charge Group', 'New charge group name:', function(btn, groupName) {
            if(btn != 'ok')
                return;

            Ext.Ajax.request({
                url: 'http://'+window.location.host+'/rest/actualCharges',
                method: 'POST',
                params: {
                    utilbill_id: selectedBill[0].get('id'),
                    rows: JSON.stringify([{
                        id: 'RSI binding required',
                        rsi_binding: 'RSI binding required',
                        group: groupName,
                        description: 'Description required',
                        quantity: 0,
                        quantity_units: 'kWh',
                        rate: 0,
                        total: 0
                    }]),
                    xaction: 'create'
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
        });
    },

    /**
     * Handle the regenerate from rate structure button being clicked.
     */ 
    regenerateFromRateStructure: function() {
        var store = this.getChargesStore(),
            selectedBill = this.getUtilityBillsGrid().getSelectionModel().getSelection();

        if (!selectedBill.length)
            return;

        Ext.Ajax.request({
            url: 'http://'+window.location.host+'/rest/refresh_charges',
            params: { utilbill_id: selectedBill[0].get('id') },
            success: function(result, request) {
                store.reload();
            },
        });
    }

});
