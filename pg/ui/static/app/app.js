Ext.Ajax.on('requestexception', function (conn, response, options) {
    if (response.status === 401) {
        Ext.Msg.alert('Error', 'Please log in!');
        window.location = 'login';
    }
});

Ext.Ajax.request({
    url: 'http://' + window.location.host + '/utilitybills/ui_configuration',
    dataType: 'json',
    success: function(response) {
        var data = Ext.JSON.decode(response.responseText);

        // TODO: we don't need these
        config.preferencesPanelDisabled = false;
        config.reportPanelDisabled = false;
        config.journalPanelDisabled = false;
        config.aboutPanelDisabled = false;
        config.chargesPanelDisabled = false;
        config.billPeriodsPanelDisabled = false;
        config.usagePeriodsPanelDisabled = false;
        config.reeBillPanelDisabled = false;
        config.utilityBillPanelDisabled = false;
        config.accountsPanelDisabled = false;
        config.paymentPanelDisabled = false;
        config.issuablePanelDisabled = false;
        config.reebillChargesPanelDisabled = false;
        config.defaultAccountSortField = false;
        config.defaultAccountSortDir = false;

        Ext.application({
            name: 'ReeBill', // TODO change
            autoCreateViewport: true,

            paths: {'ReeBill': 'static/app'},

            controllers: [
                'UtilityBills',
                'UtilityBillRegisters',
                'Charges',
                'TabPanel',
                'Viewer'
            ],

            stores: [
                'Suppliers',
                'Services',
                'Utilities',
                'RateClasses',
                'Charges',
                'Units',
                'UtilityBillRegisters',
                'UtilityBills',
                'UtilityBillsMemory', // not sure if we need this
                'Timestamps' // ???
            ],

            launch: function() {}
        });
    }
});
