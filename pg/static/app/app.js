Ext.Ajax.on('requestexception', function (conn, response, options) {
    if (response.status === 401) {
        Ext.Msg.alert('Error', 'Please log in!');
        window.location = 'login';
    }
});

Ext.application({
    name: 'ReeBill', // TODO change
    autoCreateViewport: true,

    paths: {'ReeBill': 'app'},

    controllers: [
        'UtilityBills',
        'UtilityBillRegisters',
        'Charges',
        'TabPanel',
        'Viewer'
    ],

    stores: [
        'Accounts',
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

