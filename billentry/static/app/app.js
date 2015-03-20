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
        'AccountsFilter',
        'Services',
        'Utilities',
        'RateClasses',
        'Charges',
        'Units',
        'UtilityBills'
    ],

    refs: [{
        ref: 'utilityBillViewer',
        selector: 'pdfpanel[name=utilityBillViewer]'
    },{
        ref: 'applicationTabPanel',
        selector: 'tabpanel[name=applicationTab]'
    },{
        ref: 'utilityBillsGrid',
        selector: 'grid[id=utilityBillsGrid]'
    }],

    launch: function() {
        // Application Wide keyboard shortcuts
        var map = new Ext.util.KeyMap({
            target: document,
            binding: [{
                key: "a",
                ctrl: true,
                shift: true,
                fn: function(){
                    var p = this.getUtilityBillViewer();
                    p.scrollBy(0, -p.getHeight(), true);
                },
                scope: this
            },{
                key: "z",
                ctrl: true,
                shift: true,
                fn: function(){
                    var p = this.getUtilityBillViewer();
                    p.scrollBy(0, p.getHeight(), true);
                },
                scope: this
            },{
                key: "c",
                fn: function(){
                    var activeTab = this.getApplicationTabPanel().getActiveTab();
                    var selectedBill = this.getUtilityBillsGrid().getSelectionModel().getSelection();

                    if (activeTab.name !== 'utilityBillsTab' || !selectedBill || !selectedBill.length)
                        return;

                    this.getController('Charges').handleNew();
                },
                scope: this
            }]
        });
    }
});

