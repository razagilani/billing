Ext.define('ReeBill.controller.Reebills', {
    extend: 'Ext.app.Controller',

    stores: [
        'Reebills'
    ],
    
    refs: [{
        ref: 'accountsGrid',
        selector: 'grid[id=accountsGrid]'
    },{
        ref: 'reebillsGrid',
        selector: 'grid[id=reebillsGrid]'        
    },{
        ref: 'serviceForCharges',
        selector: 'combo[name=serviceForCharges]'        
    },{
        ref: 'bindREOffsetButton',
        selector: 'button[action=bindREOffset]'        
    },{
        ref: 'computeReebillButton',
        selector: 'button[action=computeReebill]'        
    },{
        ref: 'deleteReebillButton',
        selector: 'button[action=deleteReebill]'        
    },{
        ref: 'createNewVersionButton',
        selector: 'button[action=createNewVersion]'        
    },{
        ref: 'renderPdfButton',
        selector: 'button[action=renderPdf]'        
    },{
        ref: 'emailButton',
        selector: 'button[action=email]'
    }],
    
    init: function() {
        this.application.on({
            scope: this
        });
        
        this.control({
            'panel[name=reebillsTab]': {
                activate: this.handleActivate
            },
            'grid[id=reebillsGrid]': {
                selectionchange: this.handleRowSelect
            },
            'button[action=bindREOffset]': {
                click: this.handleBindREOffset
            },
            'button[action=computeReebill]': {
                click: this.handleCompute
            },
            'button[action=deleteReebill]': {
                click: this.handleDelete
            },
            'button[action=createNewVersion]': {
                click: this.handleCreateNewVersion
            },
            'button[action=email]': {
                click: this.handleMail
            }
        });
    },

    /**
     * Handle the panel being activated.
     */
    handleActivate: function() {
        var selectedAccount = this.getAccountsGrid().getSelectionModel().getSelection();

        if (!selectedAccount.length)
            return;

        this.getReebillsStore().getProxy().setExtraParam('account', selectedAccount[0].get('account'));

        this.getReebillsStore().reload();
    },

    /**
     * Handle the row selection.
     */
    handleRowSelect: function() {
        var selections = this.getReebillsGrid().getSelectionModel().getSelection();
        if (!selections.length)
            return;

        var selectedAccounts = this.getAccountsGrid().getSelectionModel().getSelection();
        if (!selectedAccounts.length)
            return;

        var selected = selections[0];
        var selectedAccount = selectedAccounts[0];

        var sequence = selected.get('sequence');
        var issued = selected.get('issued');

        if (selected.get('services').length)
            this.getServiceForCharges().setValue(selected.get('services')[0]);

        this.getDeleteReebillButton().setDisabled(issued);
        this.getBindREOffsetButton().setDisabled(issued);
        this.getComputeReebillButton().setDisabled(issued);
        this.getRenderPdfButton().setDisabled(false);
        this.getCreateNewVersionButton().setDisabled(sequence && !issued);
    },

    /**
    * Handle the delete button.
    */
    handleMail: function() {
        var store = this.getReebillsStore();

        var selections = this.getReebillsGrid().getSelectionModel().getSelection();
        if (!selections.length)
            return;

        var selectedAccounts = this.getAccountsGrid().getSelectionModel().getSelection();
        if (!selectedAccounts.length)
            return;

        var selected = selections[0];
        selected.set('action', 'mail');
    },

    /**
     * Handle the bind RE offset button.
     */
    handleBindREOffset: function() {
        var store = this.getReebillsStore();

        var selections = this.getReebillsGrid().getSelectionModel().getSelection();
        if (!selections.length)
            return;

        var selectedAccounts = this.getAccountsGrid().getSelectionModel().getSelection();
        if (!selectedAccounts.length)
            return;

        var selected = selections[0];
        selected.set('action', 'bindree');

//        var waitMask = new Ext.LoadMask(Ext.getBody(), { msg: 'Gathering data; please wait' });
//        waitMask.show();
//
//        Ext.Ajax.request({
//            url: 'http://'+window.location.host+'/rest/bindree',
//            method: 'POST',
//            params: {
//                account: selectedAccount.get('account'),
//                sequence: selected.get('sequence')
//            },
//            success: function(response, request) {
//                var jsonData = Ext.JSON.decode(response.responseText);
//                if (jsonData.success) {
//                    store.reload();
//                } else {
//                    Ext.Msg.alert('Error', jsonData.errors.details);
//                }
//            },
//            callback: function() {
//                waitMask.hide();
//            }
//        });

     },

    /**
     * Handle the compute button.
     */
     handleCompute: function() {
        var store = this.getReebillsStore();

        var selections = this.getReebillsGrid().getSelectionModel().getSelection();
        if (!selections.length)
            return;

        var selectedAccounts = this.getAccountsGrid().getSelectionModel().getSelection();
        if (!selectedAccounts.length)
            return;

        var selected = selections[0];
        selected.set('action', 'compute');
     },

     /**
      * Handle the delete button.
      */
     handleDelete: function() {
        var store = this.getReebillsStore();

        var selections = this.getReebillsGrid().getSelectionModel().getSelection();
        if (!selections.length)
            return;

        var selectedAccounts = this.getAccountsGrid().getSelectionModel().getSelection();
        if (!selectedAccounts.length)
            return;

        var selected = selections[0];
        var selectedAccount = selectedAccounts[0];

        var msg = 'Are you sure you want to delete the latest version of reebill '
            + selectedAccount.get('account') + '-' + selected.get('sequence') + '?';

        Ext.Msg.confirm('Confirm deletion', msg, function(answer) {
            if (answer == 'yes') {
                Ext.Ajax.request({
                    url: 'http://'+window.location.host+'/rest/delete_reebill',
                    method: 'POST',
                    params: {
                        account: selectedAccount.get('account'),
                        sequences: selected.get('sequence')
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
            }
        });
     },

     /**
      * Handle the render pdf button.
      */
     handleRenderPdf: function() {
        var store = this.getReebillsStore();

        var selections = this.getReebillsGrid().getSelectionModel().getSelection();
        if (!selections.length)
            return;

        var selectedAccounts = this.getAccountsGrid().getSelectionModel().getSelection();
        if (!selectedAccounts.length)
            return;

        var selected = selections[0];
        selected.set('action', 'render');
     },

     /**
      * Handle the create new version button.
      */
     handleCreateNewVersion: function() {
        var store = this.getReebillsStore();

        var selections = this.getReebillsGrid().getSelectionModel().getSelection();
        if (!selections.length)
            return;

        var selectedAccounts = this.getAccountsGrid().getSelectionModel().getSelection();
        if (!selectedAccounts.length)
            return;

        var selected = selections[0];
        var selectedAccount = selectedAccounts[0];

        var waitMask = new Ext.LoadMask(Ext.getBody(), { msg: 'Creating new versions; please wait' });
        waitMask.show();

        Ext.Ajax.request({
            url: 'http://'+window.location.host+'/rest/new_reebill_version',
            method: 'POST',
            params: {
                account: selectedAccount.get('account'),
                sequence: selected.get('sequence')
            },
            success: function(response, request) {
                var jsonData = Ext.JSON.decode(response.responseText);
                if (jsonData.success) {
                    store.reload();
                    Ext.MessageBox.alert("New version created", jsonData.new_version);
                } else {
                    Ext.Msg.alert('Error', jsonData.errors.details);
                }
            },
            callback: function() {
                waitMask.hide();
            }
        });
     }

});
