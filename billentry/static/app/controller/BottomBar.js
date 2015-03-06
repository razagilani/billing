Ext.define('ReeBill.controller.BottomBar', {
    extend: 'Ext.app.Controller',

    stores: ['Preferences'],

    views:[
        'Viewport',
        'accounts.Accounts',
        'accounts.AccountForm'
    ],
    
    refs: [{
        ref: 'accountForm',
        selector: 'accountForm'
    },{
        ref: 'accountsGrid',
        selector: 'grid[id=accountsGrid]'
    },{
        ref: 'utilityBillsGrid',
        selector: 'grid[id=utilityBillsGrid]'
    },{
        ref: 'revisionTBLabel',
        selector: 'tbtext[name=revisionTBLabel]'
    },{
        ref: 'accountTBLabel',
        selector: 'tbtext[name=accountTBLabel]'
    },{
        ref: 'ubSequenceTBLabel',
        selector: 'tbtext[name=ubSequenceTBLabel]'
    },{
        ref: 'rbSequenceVersionTBLabel',
        selector: 'tbtext[name=rbSequenceVersionTBLabel]'
    },{
        ref: 'userTBLabel',
        selector: 'tbtext[name=userTBLabel]'
    },{
        ref: 'revisionTBLabel',
        selector: 'tbtext[name=revisionTBLabel]'
    }],
    
    init: function() {
        var me = this;
        this.application.on({
            scope: this
        });
        
        this.control({
            'grid[id=accountsGrid]': {
                selectionchange: this.handleAccountSelect
            },
            'grid[id=utilityBillsGrid]': {
                selectionchange: this.handleUtilityBillSelect
            }
        });
    },

    /**
     * Handle the account selection.
     */
    handleAccountSelect: function() {
        var selected = this.getAccountsGrid().getSelectionModel().getSelection()[0];
        if (selected){
            var aLabel = this.getAccountTBLabel();
            aLabel.setText(selected.get('account'));
            var rLabel = this.getRbSequenceVersionTBLabel();
            rLabel.setText('');
            var uLabel = this.getUbSequenceTBLabel();
            uLabel.setText('')
        }
    },

    /**
     * Handle the utilitybill selection.
     */
    handleUtilityBillSelect: function() {
        var selected = this.getUtilityBillsGrid().getSelectionModel().getSelection()[0];
        if (selected){
            var label = this.getUbSequenceTBLabel();
            label.setText(
                Ext.Date.format(selected.get('period_start'), 'Y-m-d')
                + ' to ' +
                Ext.Date.format(selected.get('period_end'), 'Y-m-d')
                + ' (UB)');
        }
    }

});
