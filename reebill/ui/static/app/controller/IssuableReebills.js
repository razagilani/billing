Ext.define('ReeBill.controller.IssuableReebills', {
    extend: 'Ext.app.Controller',

    stores: [
        'IssuableReebills', 'IssuableReebillsMemory'
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

    makeIssueRequest: function(url, billRecord){
        var me = this;
        var store = me.getIssuableReebillsStore();
        var waitMask = new Ext.LoadMask(Ext.getBody(), { msg: 'Please wait...' });
        var params = {reebills: billRecord}

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
           Ext.MessageBox.show({
                title: "Issued and Mailed " + obj.issued.length + " reebills ",
                msg:  "Mail sent successfully",
                icon: Ext.MessageBox.INFO,
                buttons: Ext.Msg.OK,
                cls: 'messageBoxOverflow'
            });
            Ext.defer(function(){
                store.reload();
                waitMask.hide();
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
            reebills: params,
            method: 'POST',
            success: function(response){
                waitMask.hide();
                var obj = Ext.JSON.decode(response.responseText);
                if (obj.corrections != undefined) {
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
                                        var reebills = new Array();
                                        Ext.each(obj.reebills, function (reebill) {
                                            if (reebill.adjustment != undefined)
                                                reebill.apply_corrections = true;
                                            reebills.push(reebill.reebill);
                                        });
                                        var params = Ext.encode(obj.reebills);
                                        var json_data = {reebills: params}
                                        Ext.Ajax.request({
                                            url: url,
                                            method: 'POST',
                                            params: json_data,
                                            reebills: json_data,
                                            failure: failureFunc,
                                            success: successFunc
                                        });
                                        waitMask.show();
                                        }

                                });

                }
                else
                {
                    successFunc(response);
                }

            },
            failure: failureFunc
        });
    },

    /**
     * Handle the issue button.
     */
    handleIssue: function() {
        var me = this;
        var selections = me.getIssuableReebillsGrid().getSelectionModel().getSelection();

        if (!selections.length)
            return;

        data = []
        Ext.each(selections, function(item){
            var obj = {
                account: item.data.account,
                sequence: item.data.sequence,
                recipients: item.data.mailto,
                apply_corrections: false
            };
            data.push(obj);
        });

        me.makeIssueRequest(window.location.origin + '/reebill/issuable/issue_and_mail', Ext.encode(data))
    },

    handleIssueProcessed: function(){
        var me = this;
        me.makeIssueRequest(window.location.origin + '/reebill/issuable/issue_processed_and_mail')
    }

});
