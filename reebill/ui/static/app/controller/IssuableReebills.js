Ext.define('ReeBill.controller.IssuableReebills', {
    extend: 'Ext.app.Controller',

    stores: [
        'IssuableReebills', 'IssuableReebillsMemory', 'CustomerGroups'
    ],

    views:[
        'issuablereebills.IssuableReebills'
    ],
    
    refs: [{
        ref: 'issuableReebillsGrid',
        selector: 'grid[id=issuableReebillsGrid]'
    },{
        ref: 'issueButton',
        selector: '[action=issue]'
    },{
        ref: 'issueProcessedButton',
        selector: '[action=issueprocessed]'
    },{
        ref: 'createSummaryButtonForSelectedBills',
        selector: '[action=createsummaryforselectedbills]'
    },{
        ref: 'createSummaryButton',
        selector: '[action=createsummaryfortag]'
    },{
        ref: 'filterBillsCombo',
        selector: '#filter_bills_combo'
    }],

    init: function() {
        this.application.on({
            scope: this
        });
        
        this.control({
            'grid[id=issuableReebillsGrid]': {
                activate: this.handleActivate,
                selectionchange: this.handleRowSelect
            },
            '[action=issue]': {
                click: this.handleIssue
            },
            '[action=issueprocessed]': {
                click: this.handleIssueProcessed
            },
            '[action=createsummaryforselectedbills]': {
                click: this.handleCreateSummaryForSelectedBills
            },
            '[action=createsummaryfortag]': {
                click: this.handleCreateSummaryForTag
            },

            '#filter_bills_combo':{
                select: this.handleFilterBillsComboChanged
            }
        });

        this.getIssuableReebillsStore().on({
            beforeload: function(store){
                var grid = this.getIssuableReebillsGrid();
                grid.setLoading(true);
            },
            load: function(store) {
                var grid = this.getIssuableReebillsGrid();
                var pButton = this.getIssueProcessedButton();
                grid.setLoading(false);
                pButton.setDisabled(store.getProccessedReebillsCount() === 0);
            },
            scope: this
        });
    },

    /**
     * Handle the panel being activated.
     */
    handleActivate: function() {
        this.getIssuableReebillsStore().reload();
        this.getCustomerGroupsStore().reload();
        this.getFilterBillsCombo().clearValue();
    },

    /**
     * Handle the row selection.
     */
    handleRowSelect: function() {
        var issuableMailListRegex = new RegExp("^[\\w!#$%&'*+\\-/=?^_`{\\|}~](\\.?[\\w!#$%&'*+\\-/=?^_`{\\|}~])*@[\\w-](\\.?[\\w-])*(,\\s*[\\w!#$%&'*+\\-/=?^_`{\\|}~](\\.?[\\w!#$%&'*+\\-/=?^_`{\\|}~])*@[\\w-](\\.?[\\w-])*)*$")

        var selections = this.getIssuableReebillsGrid().getSelectionModel().getSelection();
        var disabled = false;
        
        if (!selections.length)
            disabled = true;
        else if (!issuableMailListRegex.test(selections[0].get('mailto')))
            disabled = true;

        this.getIssueButton().setDisabled(disabled);
    },

    makeCheckCorrectionsRequest: function(bills, success_callback, failure_callback){
        console.log(bills)
        Ext.Ajax.request({
            url: window.location.origin + '/reebill/issuable/check_corrections',
            params: {reebills: bills},
            method: 'POST',
            success: function(response){
                //waitMask.hide();
                var obj = Ext.JSON.decode(response.responseText);
                if (obj.corrections) {
                    var reebill_corrections = '';
                    Ext.each(obj.reebills, function (reebill) {
                        if (reebill.adjustment != undefined) {
                            reebill_corrections +='Reebill from account ' + reebill.account+
                                     ' with sequence ' + reebill.sequence +
                                      ' with corrections '  + reebill.corrections +
                                    ' will be applied to this bill as an adjusment of $'
                                    + reebill.adjustment + '. Are you sure you want to issue it?' + '</br>'


                        }
                    });

                    Ext.MessageBox.confirm(
                        'Corrections must be applied',reebill_corrections,
                        function (answer) {
                            if (answer == 'yes') {
                                success_callback();
                            }
                    });
                } else {
                    success_callback(response);
                }
            },
            failure: failure_callback
        });
    },

    makeIssueRequest: function(url, billRecords, apply_corrections){
        var me = this;
        var store = me.getIssuableReebillsStore();

        var failureFunc = function(response){
            //waitMask.hide();
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
           Ext.MessageBox.show({
                title: "Issued and Mailed " + obj.issued.length + " reebills ",
                msg:  "Mail sent successfully",
                icon: Ext.MessageBox.INFO,
                buttons: Ext.Msg.OK,
                cls: 'messageBoxOverflow'
            });
            Ext.defer(function(){
                store.reload();
                //waitMask.hide();
            }, 1000);
        };

        this.makeCheckCorrectionsRequest(billRecords, function(){
            var params = {reebills: billRecords};
            Ext.Ajax.request({
                url: window.location.origin + '/reebill/issuable/issue_and_mail',
                method: 'POST',
                params: params,
                failure: failureFunc,
                success: successFunc
            });
        }, failureFunc);
    },

    /**
     * Handle the issue button.
     */
    handleIssue: function() {
        var me = this;
        var selections = me.getIssuableReebillsGrid().getSelectionModel().getSelection();

        if (!selections.length)
            return;

        var data = [];
        Ext.each(selections, function(item){
            var obj = {
                account: item.data.account,
                sequence: item.data.sequence,
                recipients: item.data.mailto
            };
            data.push(obj);
        });

        me.makeIssueRequest(window.location.origin + '/reebill/issuable/issue_and_mail', Ext.encode(data))
    },

    handleIssueProcessed: function(){
        var me = this;
        me.makeIssueRequest(window.location.origin + '/reebill/issuable/issue_processed_and_mail')
    },

    handleCreateSummaryForSelectedBills: function(){
        var selections = this.getIssuableReebillsGrid().getSelectionModel().getSelection();
        store = this.getIssuableReebillsStore();

        if (!selections.length){
            return
        }
        var data = [];
        Ext.each(selections, function(item){
            var obj = {
                account: item.data.account,
                sequence: item.data.sequence
            };
            data.push(obj);
        });

        var failureFunc = function(response){
            //waitMask.hide();
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
           Ext.MessageBox.show({
                title: "Issued and Mailed summary bills",
                msg:  "Mail sent successfully",
                icon: Ext.MessageBox.INFO,
                buttons: Ext.Msg.OK,
                cls: 'messageBoxOverflow'
            });
            Ext.defer(function(){
                store.reload();
            }, 1000);
        };

        this.makeCheckCorrectionsRequest(Ext.encode(data), function(){
            Ext.MessageBox.prompt('Email Recipient ', 'Please enter e-mail address of recipient:', function(btn, text){
                if (btn == 'ok'){
                    var params = {bill_dicts: Ext.encode(data), summary_recipient: text};
                    Ext.Ajax.request({
                        url: window.location.origin + '/reebill/issuable/create_summary_for_bills',
                        method: 'POST',
                        params: params,
                        failure: failureFunc,
                        success: successFunc
                    });
                }
            });
        }, failureFunc);
    },

    handleCreateSummaryForTag: function(){
        var me = this;
        var filter_combo_box = this.getFilterBillsCombo();
        var issue_all_reebills_button = this.getIssueProcessedButton();
        var selected_tag = filter_combo_box.getValue();
        var store = me.getIssuableReebillsStore();

        //var waitMask = new Ext.LoadMask(Ext.getBody(), { msg: 'Please wait...' });

        var failureFunc = function(response){
            //waitMask.hide();
            Ext.MessageBox.show({
                title: "Server error - " + response.status + " - " + response.statusText,
                msg:  response.responseText,
                icon: Ext.MessageBox.ERROR,
                buttons: Ext.Msg.OK,
                cls: 'messageBoxOverflow'
            });
            issue_all_reebills_button.enable();
            filter_combo_box.clearFilter();
        };
        var successFunc = function(response){
            // Wait for the bill to be issued before reloading the store
           var obj = Ext.JSON.decode(response.responseText);
           Ext.MessageBox.show({
                title: "Issued and Mailed summary bills",
                msg:  "Mail sent successfully",
                icon: Ext.MessageBox.INFO,
                buttons: Ext.Msg.OK,
                cls: 'messageBoxOverflow'
            });
            Ext.defer(function(){
                store.reload();
                issue_all_reebills_button.enable();
                filter_combo_box.clearValue();
                //waitMask.hide();
            }, 1000);
        };

        if (selected_tag == null || selected_tag == -1){
            Ext.MessageBox.show({
                title: "Create Summary Error",
                msg:  "You must select a tag before creating a summary of bills by tag",
                icon: Ext.MessageBox.ERROR,
                buttons: Ext.Msg.OK,
                cls: 'messageBoxOverflow'
            });
        }
        else{
            var data = [];
            Ext.each(this.getIssuableReebillsStore().getRange(), function(item){
                var obj = {
                    account: item.data.account,
                    sequence: item.data.sequence,
                    recipients: item.data.mailto
                };
                data.push(obj);
            });
            this.makeCheckCorrectionsRequest(Ext.encode(data), function(){
            Ext.MessageBox.prompt('Email Recipient ', 'Please enter e-mail address of recipient:', function(btn, text){
                if (btn == 'ok'){
                    var params = {customer_group_id: selected_tag, summary_recipient: text};

                    Ext.Ajax.request({
                        url: window.location.origin + '/reebill/issuable/issue_summary_for_customer_group',
                        method: 'POST',
                        params: params,
                        failure: failureFunc,
                        success: successFunc
                    });
                }
            });
        }, failureFunc);
            //waitMask.show()

        }


    },

    handleFilterBillsComboChanged: function(filter_bills_combo, record){
        var me = this;
        var issuable_reebills_store = Ext.getStore("IssuableReebills");
        var issue_all_reebills_button = this.getIssueProcessedButton();
        if (record[0].get('id') ==-1) {
            issuable_reebills_store.clearFilter();
            issue_all_reebills_button.enable();
        }
        else {
            issue_all_reebills_button.disable();
            issuable_reebills_store.clearFilter(true);
            name = record[0].get('name');
            issuable_reebills_store.filterBy(function (rec, id) {
                groups = rec.get('groups');
                var filter = false;
                Ext.each(groups, function (group) {
                    if (name == group['name'])
                        filter = true;

                });
                var result = filter;
                filter = false;
                return result;
            });
        }
    }

});
