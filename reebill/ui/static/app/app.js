Ext.Ajax.on('requestexception', function (conn, response, options) {
    if (response.status === 401) {
        Ext.Msg.alert('Error', 'Please log in!');
        window.location = 'login';
    }
});

Ext.Ajax.request({
    url: 'http://' + window.location.host + '/reebill/ui_configuration',
    dataType: 'json',
    success: function(response) {
        var data = Ext.JSON.decode(response.responseText);

        config.preferencesPanelDisabled = data.preferences_panel_disabled;
        config.reportPanelDisabled = data.report_panel_disabled;
        config.journalPanelDisabled = data.preferences_panel_disabled;
        config.aboutPanelDisabled = data.about_panel_disabled;
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
                'Accounts', 'IssuableReebills', 'Journal', 'Payments', 'RateStructures', 'Reports', 'Preferences',
                'ReebillCharges', 'Reebills', 'TabPanel', 'UtilityBillRegisters', 'UtilityBills', 'Viewer'
            ],
            
            stores: [
                'Accounts', 'AccountsMemory', 'AccountsFilter', 'IssuableReebills', 'EstimatedRevenue', 'Preferences',
                'JournalEntries', 'Payments', 'RateStructures', 'Reconciliations', 'ReebillCharges', 'Reebills', 
                'Services', 'Timestamps', 'Units', 'UtilityBills', 'UtilityBillRegisters', 'ReeBillVersions'
            ],

            models: [
                'Account', 'Charge', 'EstimatedRevenue', 'Preference',
                'IssuableReebill', 'JournalEntry', 'Payment', 'Reconciliation',
                'Reebill', 'ReebillCharge', 'UtilityBill', 'UtilityBillRegister'
            ],
            
            launch: function() {

            }
        });
    }
});