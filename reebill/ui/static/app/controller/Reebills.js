Ext.define('ReeBill.controller.Reebills', {
    extend: 'Ext.app.Controller',

    stores: [
        'Reebills', 'ReeBillVersions'
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
    },{
        ref: 'sequentialAccountInformationForm',
        selector: 'panel[id=sequentialAccountInformationForm]'
    },{
        ref: 'saveAccountInformationButton',
        selector: 'button[action=saveAccountInformation]'
    },{
        ref: 'resetAccountInformationButton',
        selector: 'button[action=resetAccountInformation]'
    },{
        ref: 'reeBillVersions',
        selector: 'reeBillVersions'
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
            'button[action=saveAccountInformation]': {
                click: this.handleSaveAccountInformation
            },
            'button[action=resetAccountInformation]': {
                click: this.handleResetAccountInformation
            },
            'combo[name=reeBillVersions]': {
                change: this.loadSequentialAccountInformation,
                select: this.loadSequentialAccountInformation
            },
            'panel[id=sequentialAccountInformationForm]':{
               expand: this.handleAccountInformationActivation
            }
        });

        this.getReeBillVersionsStore().on({
            beforeload: function(){
                this.getSequentialAccountInformationForm().setDisabled(true);
            },
            load: function(){
                var store = this.getReeBillVersionsStore();
                var combo = this.getReeBillVersions();
                // Select the first element
                combo.select(store.getAt(0));
                this.loadSequentialAccountInformation();
            },
            scope: this
        });
    },

    /**
     * Handle the panel being activated.
     */
    handleActivate: function() {
        var selectedAccount = this.getAccountsGrid().getSelectionModel().getSelection();
        var selections = this.getReebillsGrid().getSelectionModel().getSelection();

        if (!selectedAccount.length)
            return;

        // required for GET & POST
        this.getReebillsStore().getProxy().setExtraParam('account', selectedAccount[0].get('account'));
        this.getReebillsStore().loadPage(1);

        this.getSequentialAccountInformationForm().collapse();
        this.getSequentialAccountInformationForm().setDisabled(!selections.length);
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

        this.getDeleteReebillButton().setDisabled(issued);
        this.getBindREOffsetButton().setDisabled(issued);
        this.getComputeReebillButton().setDisabled(issued);
        this.getRenderPdfButton().setDisabled(false);
        this.getCreateNewVersionButton().setDisabled(sequence && !issued);
        this.getSequentialAccountInformationForm().setDisabled(false);
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

     },

     /**
      * Loads the ReeBillVersionsStore
      */
     handleAccountInformationActivation: function() {
         var selections = this.getReebillsGrid().getSelectionModel().getSelection();
         if (!selections.length)
             return;
         var selected = selections[0];
         var account = selected.get('account');
         var sequence = selected.get('sequence');

         // Set store parameters for ReebillVersions
         var versionStore = this.getReeBillVersionsStore();
         var params = {
             account: account,
             sequence: sequence
         }
         versionStore.getProxy().extraParams = params;

         // Only reload if the store doens't already contain bills of the current accounts/sequence
         var record = versionStore.getAt(0)
         if(record === undefined || record.get('account') !== account || record.get('sequence') !== sequence)
            versionStore.reload();
     },

     /**
      * Loads Sequential Account Information into the form from the
      * currently selected Reebill
      */
     loadSequentialAccountInformation: function() {
         var combo = this.getReeBillVersions();
         var store = this.getReeBillVersionsStore();
         var version = combo.getValue()

         var selected = store.getAt(store.find('version', version));

         var form = this.getSequentialAccountInformationForm(),
             discount_rate = form.down('[name=discount_rate]'),
             late_charge_rate = form.down('[name=late_charge_rate]'),
             ba_addressee = form.down('[name=ba_addressee]'),
             ba_street = form.down('[name=ba_street]'),
             ba_city = form.down('[name=ba_city]'),
             ba_state = form.down('[name=ba_state]'),
             ba_postal_code = form.down('[name=ba_postal_code]'),
             sa_addressee = form.down('[name=sa_addressee]'),
             sa_street = form.down('[name=sa_street]'),
             sa_city = form.down('[name=sa_city]'),
             sa_state = form.down('[name=sa_state]'),
             sa_postal_code = form.down('[name=sa_postal_code]');

         discount_rate.setValue(selected.get('discount_rate'));
         late_charge_rate.setValue(selected.get('late_charge_rate'));
         ba_addressee.setValue(selected.get('billing_address').addressee);
         ba_street.setValue(selected.get('billing_address').street);
         ba_city.setValue(selected.get('billing_address').city);
         ba_state.setValue(selected.get('billing_address').state);
         ba_postal_code.setValue(selected.get('billing_address').postal_code);
         sa_addressee.setValue(selected.get('service_address').addressee);
         sa_street.setValue(selected.get('service_address').street);
         sa_city .setValue(selected.get('service_address').city);
         sa_state.setValue(selected.get('service_address').state);
         sa_postal_code.setValue(selected.get('service_address').postal_code);

         form.setDisabled(false);

         // Disable Save Button if not the Highest Version is selected
         // or if the bill is issued
         this.getSaveAccountInformationButton().setDisabled(
             !store.isHighestVersion(version) || selected.get('issued'));
     },

     /**
      * Handles the click of the Save button in the Sequential Account
      * Information panel
      */
     handleSaveAccountInformation: function() {
         var selections = this.getReebillsGrid().getSelectionModel().getSelection();
         if (!selections.length)
             return;
         var selected = selections[0];
         var store = this.getReebillsStore();

         var form = this.getSequentialAccountInformationForm(),
             discount_rate = form.down('[name=discount_rate]'),
             late_charge_rate = form.down('[name=late_charge_rate]'),
             ba_addressee = form.down('[name=ba_addressee]'),
             ba_street = form.down('[name=ba_street]'),
             ba_city = form.down('[name=ba_city]'),
             ba_state = form.down('[name=ba_state]'),
             ba_postal_code = form.down('[name=ba_postal_code]'),
             sa_addressee = form.down('[name=sa_addressee]'),
             sa_street = form.down('[name=sa_street]'),
             sa_city = form.down('[name=sa_city]'),
             sa_state = form.down('[name=sa_state]'),
             sa_postal_code = form.down('[name=sa_postal_code]');

         var ba = {
             addressee: ba_addressee.getValue(),
             street: ba_street.getValue(),
             city: ba_city.getValue(),
             state: ba_state.getValue(),
             postal_code: ba_postal_code.getValue()
         }
         var sa = {
             addressee: sa_addressee.getValue(),
             street: sa_street.getValue(),
             city: sa_city.getValue(),
             state: sa_state.getValue(),
             postal_code: sa_postal_code.getValue()
         }

         store.suspendAutoSync();
         selected.set('billing_address', ba);
         selected.set('service_address', sa);
         selected.set('late_charge_rate', late_charge_rate.getValue());
         selected.set('discount_rate', discount_rate.getValue());
         store.resumeAutoSync();
         store.sync();
     },

     /**
      * Handles the click of the Reset button in the Sequential Account
      * Information panel
      */
     handleResetAccountInformation: function() {
        this.loadSequentialAccountInformation();
     }
});
