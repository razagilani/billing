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
        config.chargesPanelDisabled = data.charges_panel_disabled;
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
                'BottomBar', 'Accounts', 'IssuableReebills', 'Journal', 'Payments', 'Charges', 'Reports', 'Preferences',
                'ReebillCharges', 'Reebills', 'TabPanel', 'UtilityBillRegisters', 'UtilityBills', 'Viewer'
            ],
            
            stores: [
                'Accounts', 'AccountsMemory', 'AccountsFilter', 'IssuableReebills', 'IssuableReebillsMemory', 'EstimatedRevenue', 'Preferences',
                'JournalEntries', 'Payments', 'Charges', 'RateClasses', 'Reconciliations', 'ReebillCharges', 'Reebills', 'Suppliers', 'Utilities',
                'Services', 'ServiceTypes', 'Timestamps', 'Units', 'UtilityBills', 'UtilityBillsMemory', 'UtilityBillRegisters', 'ReeBillVersions'
            ],

            models: [
                'Account', 'Charge', 'EstimatedRevenue', 'Preference',
                'JournalEntry', 'Payment', 'RateClass', 'Reconciliation', 'Supplier', 'Utility',
                'Reebill', 'ReebillCharge', 'UtilityBill', 'UtilityBillRegister'
            ],
            
            launch: function() {

            }
        });
    }
});