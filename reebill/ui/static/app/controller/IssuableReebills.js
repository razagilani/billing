Ext.define('ReeBill.controller.IssuableReebills', {
    extend: 'Ext.app.Controller',

    stores: [
        'IssuableReebills'
    ],
    
    refs: [{
        ref: 'issuableReebillsGrid',
        selector: 'grid[id=issuableReebillsGrid]'
    },{
        ref: 'issueButton',
        selector: 'button[action=issue]'
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
            'button[action=issue]': {
                click: this.handleIssue
            }
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

    makeIssueRequest: function(url){
        var me = this;
        var selections = me.getIssuableReebillsGrid().getSelectionModel().getSelection();
        if (!selections.length)
            return;

        var selected = selections[0];
        var store = me.getIssuableReebillsStore();

        var waitMask = new Ext.LoadMask(Ext.getBody(), { msg: 'Please wait...' });
        waitMask.show();

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
            store.reload();
            waitMask.hide();
        }
        Ext.Ajax.request({
            url: url,
            params: {
                account: selected.get('account'),
                sequence: selected.get('sequence'),
                mailto: selected.get('mailto'),
                apply_corrections: false
            },
            success: function(response){
                waitMask.hide();
                var obj = Ext.JSON.decode(response.responseText);
                if (obj.unissued_corrections.length){
                    Ext.MessageBox.confirm(
                        'Corrections must be applied',
                        'Corrections from reebills ' + obj.unissued_corrections +
                        ' will be applied to this bill as an adjusment of $'
                        + obj.adjustment + '. Are you sure you want to issue it?',
                        function(answer){
                            if(answer == 'yes'){
                                waitMask.show();
                                Ext.Ajax.request({
                                    url: url,
                                    params: {
                                        account: selected.get('account'),
                                        sequence: selected.get('sequence'),
                                        mailto: selected.get('mailto'),
                                        apply_corrections: true
                                    },
                                    failure: failureFunc,
                                    success: successFunc
                                });
                            }
                        }
                    );
                }else {
                    successFunc();
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
        me.makeIssueRequest(window.location.origin + '/reebill/issuable/issue_and_mail')
    }

});
