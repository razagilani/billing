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

    /**
     * Handle the issue button.
     */
    handleIssue: function() {
        var selections = this.getIssuableReebillsGrid().getSelectionModel().getSelection();
        if (!selections.length)
            return;

        var selected = selections[0];
        var store = this.getIssuableReebillsStore();

        var waitMask = new Ext.LoadMask(Ext.getBody(), { msg: 'Please wait...' });
        waitMask.show();

        store.suspendAutoSync();
        selected.set('action', 'issuemail');
        store.sync({success: function(){
            var corrections = selected.get('unissued_corrections');
            console.log(corrections, Boolean(corrections), typeof(corrections));

            waitMask.hide();
        },
        failure:function(){
            waitMask.hide();
        }})
        store.resumeAutoSync();

    }

});
