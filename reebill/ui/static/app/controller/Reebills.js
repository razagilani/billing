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
    },{
        ref: 'createNextButton',
        selector: 'button[action=createNext]'
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
            },
            'button[action=renderPdf]': {
                click: this.handleRenderPdf
            },
            'button[action=createNext]': {
                click: this.handleCreateNext
            },
        });
    },

    /**
     * Handle the panel being activated.
     */
    handleActivate: function() {
        var selectedAccount = this.getAccountsGrid().getSelectionModel().getSelection();

        if (!selectedAccount.length)
            return;

        // required for GET
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
        var me = this;
        var store = this.getReebillsStore();

        var selections = this.getReebillsGrid().getSelectionModel().getSelection();
        if (!selections.length)
            return;

        var selectedAccounts = this.getAccountsGrid().getSelectionModel().getSelection();
        if (!selectedAccounts.length)
            return;

        var selected = selections[0];

        // Prompt for email address input
        var previousInput = this.previousInput === undefined ? '' : this.previousInput;
        Ext.Msg.prompt(
            'Enter Recipients',
            'Please enter a comma separated list of email addresses',
            function(button, value, idk){
                if(button == 'ok'){

                    // Validate input
                    var validationFailed = false;
                    var emailArr = value.split(',');
                    for(var i=0; i<emailArr.length; i++){
                        if(!Ext.data.validations.email({}, emailArr[i].trim())){
                            validationFailed = true;
                        }
                    }

                    if(!validationFailed){
                        selected.beginEdit();
                        selected.set('action_value', value);
                        selected.set('action', 'mail');
                        selected.endEdit();
                    }else{
                        this.previousInput = value;
                        Ext.Msg.show({
                            title: 'Error',
                            msg: 'At least one of the email addresses you entered was not valid',
                            buttons: Ext.Msg.OK,
                            icon: Ext.window.MessageBox.ERROR
                        });
                    }
                }
            },
            me,           // scope
            false,        // multiline input
            previousInput // default input value
        )
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
                store.remove(selected);
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

        var waitMask = new Ext.LoadMask(Ext.getBody(), { msg: 'Creating new versions; please wait' });
        selected.set('action', 'newversion');
     },

     /**
      * Handle the create next version button.
      */
     handleCreateNext: function() {
        var store = this.getReebillsStore();
        store.add({issued:false});
     }

});
