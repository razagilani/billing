Ext.Ajax.on('requestexception', function (conn, response, options) {
    if (response.status === 401) {
        window.location = '/';
    }
});

Ext.application({
    name: 'BillEntry',
    autoCreateViewport: true,

    paths: {'BillEntry': 'app'},

    controllers: [
        'UtilityBills',
        'Charges',
        'Viewer',
        'Reports'
    ],

    stores: [
        'Accounts',
        'AccountsFilter',
        'Services',
        'Utilities',
        'RateClasses',
        'Charges',
        'Suppliers',
        'SupplyGroups',
        'Units',
        'UtilityBills',
        'UserUtilBillCounts',
        'UserUtilityBills',
        'AllFlaggedUtilityBills'
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
                fn: function(key, eventObj){
                    // Don't do anything if the event was received in a input
                    // field or a textarea
                    var targetTagName = eventObj.target.tagName.toLowerCase();
                    if (targetTagName == 'input' || targetTagName == 'textarea'){
                        return;
                    }

                    // Make sure the user is looking at the Utilbills tab and
                    // has a bill selected
                    var activeTab = this.getApplicationTabPanel().getActiveTab();
                    var selectedBill = this.getUtilityBillsGrid().getSelectionModel().getSelection();
                    if (activeTab.name !== 'utilityBillsTab' || !selectedBill || !selectedBill.length)
                        return;

                    // Create a new charge
                    this.getController('Charges').handleNew();
                },
                scope: this
            }]
        });
    }
});

