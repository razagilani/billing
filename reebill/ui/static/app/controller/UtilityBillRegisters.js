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
        ref: 'utilityBillVersions',
        selector: 'utilityBillVersions'
    },{
        ref: 'removeUtilityBillRegisterButton',
        selector: 'button[action=removeUtilityBillRegister]'
    },{
        ref: 'uploadIntervalMeterForm',
        selector: 'uploadIntervalMeter'
    }],    

    init: function() {
        this.application.on({
            scope: this
        });
        
        this.control({
            'panel[name=metersTab]': {
                activate: this.handleActivate
            },
            'grid[id=utilityBillRegistersGrid]': {
                selectionchange: this.handleRowSelect,
                beforeedit: this.handleStartEdit,
                canceledit: this.handleRowSelect,
                edit: this.handleEdit
            },
            'button[action=newUtilityBillRegister]': {
                click: this.handleNew
            },
            'button[action=removeUtilityBillRegister]': {
                click: this.handleDelete
            },
            'utilityBillVersions': {
                select: this.syncVersions
            },
            'button[action=resetUploadIntervalMeter]': {
                click: this.resetUploadIntervalMeter
            },
            'button[action=submitUploadIntervalMeter]': {
                click: this.submitUploadIntervalMeter
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
            utilbill_id: selectedBill[0].get('id')
        }

        if (selectedVersion !== '') {
            var versionRec = this.getUtilityBillVersions().findRecordByValue(selectedVersion);
            params.reebill_sequence = versionRec.get('sequence');
            params.reebill_version = versionRec.get('version');
        }


        this.getUtilityBillRegistersStore().load({
            params: params
        });
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
     * Handle the start of a row edit.
     */
    handleStartEdit: function() {
        this.getRemoveUtilityBillRegisterButton().setDisabled(true);
    },

    /**
     * Handle the edit of a row.
     */
    handleEdit: function(editor, e) {
        var updated = e.record,
            store = this.getUtilityBillRegistersStore(),
            selectedAccount = this.getAccountsGrid().getSelectionModel().getSelection(),
            selectedBill = this.getUtilityBillsGrid().getSelectionModel().getSelection();

        var updateProperties = Object.getOwnPropertyNames(updated.modified);

        if (!updated || updateProperties.length === 0)
            return;

        var rows = {};
        rows[updateProperties[0]] = updated.get(updateProperties[0]);
        rows.id = updated.get('id');

        var params =  {
            xaction: 'update',
            account: selectedAccount[0].get('account'),
            utilbill_id: selectedBill[0].get('id'),
            current_selected_id: updated.get('id'),
            rows: JSON.stringify([rows])
        };

        Ext.Ajax.request({
            url: 'http://'+'reebill-demo.skylineinnovations.net'+'/reebill/utilbill_registers',
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
     * Handle the new utitlity bill button being clicked.
     */
    handleNew: function() {
        var store = this.getUtilityBillRegistersStore(),
            selectedAccount = this.getAccountsGrid().getSelectionModel().getSelection(),
            selectedBill = this.getUtilityBillsGrid().getSelectionModel().getSelection();

        if (!selectedAccount || !selectedAccount.length || !selectedBill || !selectedBill.length)
            return;

        Ext.Ajax.request({
            url: 'http://'+'reebill-demo.skylineinnovations.net'+'/reebill/utilbill_registers',
            method: 'POST',
            params: {
                xaction: 'create',
                account: selectedAccount[0].get('account'),
                utilbill_id: selectedBill[0].get('id'),
                rows: '[{}]'
            },
            success: function() {
                store.load({
                    params: {
                        account: selectedBill[0].get('account'),
                        utilbill_id: selectedBill[0].get('id')
                    }
                });
            }
        });
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

        Ext.Ajax.request({
            url: 'http://'+'reebill-demo.skylineinnovations.net'+'/reebill/utilbill_registers',
            method: 'POST',
            params: {
                xaction: 'destroy',
                account: selectedAccount[0].get('account'),
                utilbill_id: selectedBill[0].get('id'),
                current_selected_id: selectedUtilityBillRegister[0].get('id'),
                rows: '["' + selectedUtilityBillRegister[0].get('id') + '"]'
            },
            success: function() {
                store.reload();
            }
        });
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
     * Handle the reset upload meter CSV button.
     */
    resetUploadIntervalMeter: function() {
        this.getUploadIntervalMeterForm().getForm().reset();
    },

    /**
     * Handle the submit upload meter CSV button.
     */
    submitUploadIntervalMeter: function () {
        var form = this.getUploadIntervalMeterForm().getForm(),
            selectedAccount = this.getAccountsGrid().getSelectionModel().getSelection(),
            selectedUtilityBillRegister = this.getUtilityBillRegistersGrid().getSelectionModel().getSelection(),
            selectedVersion = this.getUtilityBillVersions().getValue();

        if (!selectedUtilityBillRegister.length)
            return;

        if (!form.isValid()) {
            Ext.MessageBox.alert('Errors', 'Please fix form errors noted.');
            return;
        }

        var params = {
            account: selectedAccount[0].get('account'),
            register_identifier: selectedUtilityBillRegister[0].get('register_id')
        };

        if (selectedVersion !== '')
            params.sequence = this.getUtilityBillVersions().findRecordByValue(selectedVersion).get('sequence');
        else
            params.sequence = '';

        form.submit({
            url: 'http://'+'reebill-demo.skylineinnovations.net'+'/reebill/upload_interval_meter_csv',
            params: params, 
            waitMsg:'Saving...',
            failure: function(form, action) {
                switch (action.failureType) {
                case Ext.form.Action.CLIENT_INVALID:
                    Ext.Msg.alert('Failure', 'Form fields may not be submitted with invalid values');
                    break;
                case Ext.form.Action.CONNECT_FAILURE:
                    Ext.Msg.alert('Failure', 'Ajax communication failed');
                    break;
                }
            }
        });
    }

});
