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
        'Charges',
        'Viewer'
    ],

    stores: [
        'Accounts',
        'Services',
        'Utilities',
        'RateClasses',
        'Charges',
        'Units',
        'UtilityBills'
    ],

    launch: function() {}
});

