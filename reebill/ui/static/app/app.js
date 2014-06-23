Ext.Ajax.request({
    url: 'http://' + 'reebill-demo.skylineinnovations.net' + '/reebill/ui_configuration',
    dataType: 'json',
    success: function(response) {
        var data = Ext.JSON.decode(response.responseText);

        config.mailPanelDisabled = data.mail_panel_disabled;
        config.preferencesPanelDisabled = data.preferences_panel_disabled;
        config.reportPanelDisabled = data.report_panel_disabled;
        config.journalPanelDisabled = data.preferences_panel_disabled;
        config.aboutPanelDisabled = data.about_panel_disabled;
        config.chargeItemsPanelDisabled = data.charge_items_panel_disabled;
        config.rateStructurePanelDisabled = data.rate_structure_panel_disabled;
        config.billPeriodsPanelDisabled = data.bill_periods_panel_disabled;
        config.usagePeriodsPanelDisabled = data.usage_periods_panel_disabled;
        config.reeBillPanelDisabled = data.reebill_panel_disabled;
        config.utilityBillPanelDisabled = data.utility_bill_panel_disabled;
        config.accountsPanelDisabled = data.accounts_panel_disabled;
        config.paymentPanelDisabled = data.payment_panel_disabled;
        config.issuablePanelDisabled = data.issuable_panel_disabled;
        config.reebillChargesPanelDisabled = data.reebill_charges_panel_disabled;
        config.defaultAccountSortField = data.default_account_sort_field;
        config.defaultAccountSortDir = data.default_account_sort_dir;

        // Create the application.
        Ext.application({
            name: 'ReeBill',
            autoCreateViewport: true,
            
            controllers: [
                'Accounts', 'Charges', 'IssuableReebills', 'Journal', 'Mail', 'Payments', 'RateStructures', 
                'ReebillCharges', 'Reebills', 'TabPanel', 'UtilityBillRegisters', 'UtilityBills', 'Viewer'
            ],
            
            stores: [
                'Accounts', 'AccountsReeValue', 'AccountTemplates', 'Charges', 'IssuableReebills', 
                'JournalEntries', 'Payments', 'RateStructures', 'Reconciliations', 'ReebillCharges', 'Reebills', 
                'Services', 'Timestamps', 'Units', 'UtilityBills', 'UtilityBillRegisters', 'UtilityBillVersions'
            ],

            models: [
                'Account', 'AccountReeValue', 'AccountTemplate', 'Charge', 
                'IssuableReebill', 'JournalEntry', 'Payment', 'RateStructure', 'Reconciliation', 
                'Reebill', 'ReebillCharge', 'UtilityBill', 'UtilityBillRegister'
            ],
            
            launch: function() {

            }
        });
    },
    failure: function() {
        Ext.Msg.alert('Error', 'Failed to load UI configuration from the server');
    }
});