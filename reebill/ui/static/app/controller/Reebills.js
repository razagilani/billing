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
        selector: '[action=bindREOffset]'
    },{
        ref: 'computeReebillButton',
        selector: '[action=computeReebill]'
    },{
        ref: 'updateReadingsButton',
        selector: '[action=updateReadings]'
    },{
        ref: 'deleteReebillButton',
        selector: '[action=deleteReebill]'
    },{
        ref: 'createNewVersionButton',
        selector: '[action=createNewVersion]'
    },{
        ref: 'renderPdfButton',
        selector: '[action=renderPdf]'
    },{
        ref: 'emailButton',
        selector: '[action=email]'
    },{
        ref: 'createNextButton',
        selector: '[action=createNext]'
    },{
        ref: 'toggleReebillProcessedButton',
        selector: '[action=toggleReebillProcessed]'
    },{
        ref: 'sequentialAccountInformationForm',
        selector: 'panel[id=sequentialAccountInformationForm]'
    },{
        ref: 'saveAccountInformationButton',
        selector: '[action=saveAccountInformation]'
    },{
        ref: 'resetAccountInformationButton',
        selector: '[action=resetAccountInformation]'
    },{
        ref: 'reeBillVersions',
        selector: 'reeBillVersions'
    },{
        ref: 'reebillViewer',
        selector: 'pdfpanel[name=reebillViewer]'
    },{
        ref: 'uploadIntervalMeterForm',
        selector: 'uploadIntervalMeter'
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
            '[action=bindREOffset]': {
                click: this.handleBindREOffset
            },
            '[action=computeReebill]': {
                click: this.handleCompute
            },
            '[action=deleteReebill]': {
                click: this.handleDelete
            },
            '[action=createNewVersion]': {
                click: this.handleCreateNewVersion
            },
            '[action=email]': {
                click: this.handleMail
            },
            '[action=renderPdf]': {
                click: this.handleRenderPdf
            },
            '[action=createNext]': {
                click: this.handleCreateNext
            },
            '[action=saveAccountInformation]': {
                click: this.handleSaveAccountInformation
            },
            '[action=resetAccountInformation]': {
                click: this.handleResetAccountInformation
            },
            '[action=updateReadings]': {
                click: this.handleUpdateReadings
            },
            '[action=toggleReebillProcessed]': {
                click: this.handleToggleReebillProcessed
            },
            'combo[name=reeBillVersions]': {
                change: this.loadSequentialAccountInformation,
                select: this.loadSequentialAccountInformation
            },
            'panel[id=sequentialAccountInformationForm]':{
               expand: this.handleAccountInformationActivation
            },
            'button[action=resetUploadIntervalMeter]': {
                click: this.resetUploadIntervalMeter
            },
            'button[action=submitUploadIntervalMeter]': {
                click: this.submitUploadIntervalMeter
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
        var reebillsGrid = this.getReebillsGrid();
        var uploadIntervalMeterForm = this.getUploadIntervalMeterForm();
        var sequentialAccountInformationForm = this.getSequentialAccountInformationForm();

        if (!selectedAccount.length)
            return;

        // required for GET & POST
        this.getReebillsStore().getProxy().setExtraParam('account', selectedAccount[0].get('account'));
        this.getReebillsGrid().expand();
        sequentialAccountInformationForm.setDisabled(true);
        uploadIntervalMeterForm.setDisabled(true);
        this.getReebillsStore().loadPage(1, {callback: function() {
            var selections = reebillsGrid.getSelectionModel().getSelection();
            sequentialAccountInformationForm.setDisabled(!selections.length);
            uploadIntervalMeterForm.setDisabled(!selections.length);
        }});
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
        var processed = selected.get('processed')

        this.getDeleteReebillButton().setDisabled(issued);
        this.getDeleteReebillButton().setDisabled(processed);
        this.getBindREOffsetButton().setDisabled(issued);
        this.getBindREOffsetButton().setDisabled(processed);
        this.getComputeReebillButton().setDisabled(issued);
        this.getComputeReebillButton().setDisabled(processed);
        this.getToggleReebillProcessedButton().setDisabled(issued);
        this.getUpdateReadingsButton().setDisabled(issued);
        this.getRenderPdfButton().setDisabled(false);
        this.getCreateNewVersionButton().setDisabled(sequence && !issued);
        this.getSequentialAccountInformationForm().setDisabled(false);
        this.initializeUploadIntervalMeterForm();
        this.getUploadIntervalMeterForm().setDisabled(issued);
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
     * Handle the update readings button.
     */
     handleUpdateReadings: function(){
        var selected = this.getReebillsGrid().getSelectionModel().getSelection()[0];
        Ext.Msg.confirm(
            'Confirm Updating Readings',
            'Are you sure you want to update the Readings?',
            function(answer) {
                if (answer == 'yes') {
                    selected.set('action', 'updatereadings');
                }
            }
        );
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
         var me = this;
         var store = this.getReebillsStore();

         var selections = this.getReebillsGrid().getSelectionModel().getSelection();
         if (!selections.length)
             return;

         var selectedAccounts = this.getAccountsGrid().getSelectionModel().getSelection();
         if (!selectedAccounts.length)
             return;

         var selected = selections[0];
         var viewer = me.getReebillViewer();
         viewer.setLoading();
         store.suspendAutoSync();
         selected.set('action', 'render');
         store.sync({callback: function(){
              // Rerequest the document and regenerate the bust cache param
             viewer.getDocument(true);
         }});
         store.resumeAutoSync();
     },

     /**
       * Handle the toggle processed button.
       */
     handleToggleReebillProcessed: function(){
         var store = this.getReebillsStore();

         var selections = this.getReebillsGrid().getSelectionModel().getSelection();
         if (!selections.length)
             return;

         var selectedAccounts = this.getAccountsGrid().getSelectionModel().getSelection();
         if (!selectedAccounts.length)
             return;

         var selected = selections[0];
         selected.data.apply_corrections = false;
         var account = this.getAccountsGrid().getSelectionModel().getSelection();
         this.makeIssueRequest.call(this, 'http://'+window.location.host+'/reebill/reebills/toggle_processed', selected, account);
         /*selected.beginEdit();
         selected.set('action', 'setProcessed');
         selected.set('action_value', !selected.get('processed'));
         selected.endEdit();*/
     },

     makeIssueRequest: function(url, billRecord, account){
        var me = this;
        //var store = me.getIssuableReebillsStore();
        var waitMask = new Ext.LoadMask(Ext.getBody(), { msg: 'Please wait...' });
        var params = {reebill: Ext.encode(billRecord.data),
                    account: Ext.encode(account[0].data)}
        var store = this.getReebillsStore();

        var failureFunc = function(response){
            waitMask.hide();
            Ext.MessageBox.show({
                title: "Server error - " + response.status + " - " + response.statusText,
                msg:  response.responseText,
                icon: Ext.MessageBox.ERROR,
                buttons: Ext.Msg.OK,
                cls: 'messageBoxOverflow'
            });
        };
        var successFunc = function(response){
            // Wait for the bill to be issued before reloading the store
            var obj = Ext.JSON.decode(response.responseText);
            Ext.defer(function(){
                store.loadPage(1, {
                    scope: me,
                    callback: function(){
                        /*
                        this is being done in the following way because of the bug reported here
                        http://www.sencha.com/forum/showthread.php?261111-4.2.1.x-SelectionModel-in-Grid-returns-incorrect-data/page2
                        this bug is fixed in extjs 4.2.3 and higher
                         */
                        var selections = this.getReebillsGrid().getSelectionModel().getSelection();
                        var node = this.getReebillsStore().find('id', selections[0].getId());
                        this.getReebillsGrid().getSelectionModel().deselectAll();
                        this.getReebillsGrid().getSelectionModel().select(node);
                        selections = this.getReebillsGrid().getSelectionModel().getSelection();
                        var processed = selections[0].get('processed');
                        this.getDeleteReebillButton().setDisabled(processed);
                        this.getBindREOffsetButton().setDisabled(processed);
                        this.getComputeReebillButton().setDisabled(processed);
                        waitMask.hide();
                    }
                });
            }, 1000);
        }

        /*if(billRecord !== undefined){
            params.account = billRecord.get('account');
            params.sequence = billRecord.get('sequence');
            params.mailto = billRecord.get('mailto');
        }*/

        waitMask.show();
        Ext.Ajax.request({
            url: url,
            params: params,
            reebill: params,
            method: 'POST',
            success: function(response){
                waitMask.hide();
                var obj = Ext.JSON.decode(response.responseText);
                if (obj.corrections != undefined) {
                    var reebill_corrections = '';
                        if (obj.adjustment != undefined) {
                            Ext.each(obj.unissued_corrections, function(correction) {
                                reebill_corrections += 'Reebill from account ' + obj.reebill.account +
                                    ' with sequence ' + obj.reebill.sequence +
                                    ' with corrections ' + correction +
                                    ' will be applied to this bill as an adjusment of $'
                                    + obj.adjustment + ', which would also become processed.' +
                                    'Do you want to make this correction processed?' + '</br>'
                            });

                        }

                    Ext.MessageBox.confirm(
                                'There are corrections with this reebill',reebill_corrections,

                                function (answer) {
                                    if (answer == 'yes') {
                                            if (obj.adjustment != undefined)
                                                obj.reebill.apply_corrections = true;

                                        var params = {reebill: Ext.encode(obj.reebill),
                                                    account: Ext.encode(account[0].data)}
                                        Ext.Ajax.request({
                                            url: url,
                                            method: 'POST',
                                            params: params,
                                            failure: failureFunc,
                                            success: successFunc,
                                            scope: this
                                        });
                                        waitMask.show();
                                        }

                                });
                    store.reload();
                }
                else
                {
                    successFunc(response);
                }

            },
            failure: function() {
                failureFunc(this)
            },
            scope: this
        });
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

         var waitMask = new Ext.LoadMask(Ext.getBody(),
             { msg: 'Creating new version. Please wait...' });
         selected.set('action', 'newversion');
         waitMask.show();

         // We have to releoad the store, because the new version will be a
         // completely new Reebill, with a new id
         Ext.Function.defer(function(){
             store.reload();
             waitMask.hide();
         }, 1000, this);
     },

     /**
      * Handle the create next version button.
      */
     handleCreateNext: function() {
         var store = this.getReebillsStore();
         if(store.count() === 0){
            if(this._lastCreateNextDate === undefined){
                this._lastCreateNextDate = ''
            }
            Ext.Msg.prompt(
                'Service Start Date',
                'Enter the date (YYYY-MM-DD) on which\n your utility service(s) started',
                function(button, text){
                    if(button === 'ok'){
                        var controller = this;
                        controller._lastCreateNextDate = text;
                        if(Ext.Date.parse(text, 'Y-m-d') !== undefined) {
                            store.insert(0, {period_start: text});
                        }else{
                            Ext.Msg.alert(
                                'Invalid Date',
                                'Please enter a date in the format (YYYY-MM-DD)',
                                function(){
                                    controller.handleCreateNext();
                                }
                            )
                        }
                    }
                },
                this,
                false,
                this._lastCreateNextDate
            )
         }else{
            store.insert(0, {issued:false});
         }
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
             !store.isHighestVersion(version) || selected.get('issued') || selected.get('processed'));
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
     },

    /**
     * Initialize the upload form
     */
    initializeUploadIntervalMeterForm: function() {
        var form = this.getUploadIntervalMeterForm();
        var selectedReebill = this.getReebillsGrid().getSelectionModel().getSelection();
        var registerBindingField = form.down('[name=register_binding]');

        form.getForm().reset();

        var readings = selectedReebill[0].get('readings');
        var energySoldRegister = null;
        for (var i = 0;i < readings.length; i++) {
            if (readings[i].measure == 'Energy Sold') {
                energySoldRegister = readings[i].register_binding;
            }
        }
        if (energySoldRegister != null) {
            registerBindingField.setValue(energySoldRegister);
        }
    },

    /**
     * Handle the reset upload meter CSV button.
     */
    resetUploadIntervalMeter: function() {
        this.initializeUploadIntervalMeterForm();
    },

    /**
     * Handle the submit upload meter CSV button.
     */
    submitUploadIntervalMeter: function () {
        var form = this.getUploadIntervalMeterForm().getForm(),
        selectedAccount = this.getAccountsGrid().getSelectionModel().getSelection(),
        selectedReebill = this.getReebillsGrid().getSelectionModel().getSelection();

        if (!selectedReebill.length) {
            Ext.MessageBox.alert('Errors', 'Please select a reebill to apply this to..');
            return;
        }

        if (!form.isValid()) {
            Ext.MessageBox.alert('Errors', 'Please fix form errors noted.');
            return;
        }

        var params = {
            account: selectedAccount[0].get('account'),
            sequence: selectedReebill[0].get('sequence'),
        };

        form.submit({
            url: 'http://'+window.location.host+'/reebill/reebills/upload_interval_meter_csv',
            params: params, 
            waitMsg:'Saving...',
            failure: function(form, action) {
                Ext.Msg.alert('Error', 'Failed to submit interval meter data')
            }
        });
    }

});
