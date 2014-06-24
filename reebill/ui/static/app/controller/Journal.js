Ext.define('ReeBill.controller.Journal', {
    extend: 'Ext.app.Controller',

    stores: [
        'JournalEntries'
    ],
    
    refs: [{
        ref: 'noteForm',
        selector: 'noteForm'
    },{
        ref: 'accountsGrid',
        selector: 'grid[id=accountsGrid]'
    },{
        ref: 'journalEntriesGrid',
        selector: 'grid[id=journalEntriesGrid]'
    }],    
    
    init: function() {
        this.application.on({
            scope: this
        });
                
        this.control({
            'panel[name=journalTab]': {
                activate: this.handleActivate
            },
            'button[action=handleNoteSubmit]': {
                click: this.handleSubmit
            },
            'button[action=handleNoteReset]': {
                click: this.handleNoteReset
            }
        });
    },

    /**
     * Handle the submit button being clicked.
     */
    handleSubmit: function() {
        var scope = this;

        var selectedAccount = scope.getAccountsGrid().getSelectionModel().getSelection()[0];

        this.getNoteForm().getForm().submit({
            url: 'http://'+window.location.host+'/rest/save_journal_entry',
            params: {
                account: selectedAccount.get('account'),
                sequence: null
            },            
            success: function() {
                scope.getNoteForm().getForm().reset();
            },
            failure: function(form, action) {
                Ext.Msg.alert('Error', 'Error uploading note.')
            }
        }); 
    },

    /**
     * Handle the cancel button being clicked.
     */
    handleNoteReset: function() {
        this.getNoteForm().getForm().reset(); 
    },

    /**
     * Handle the panel being activated.
     */
    handleActivate: function() {
        var selectedAccount = this.getAccountsGrid().getSelectionModel().getSelection();
        var account = null;

        if (selectedAccount.length) {
            account = selectedAccount[0].get('account');
        }

        var title = account ? 'Journal Entries for Account ' + account : 'Journal Entries';

        this.getJournalEntriesGrid().setTitle(title);

        if (!account)
            return;

        this.getJournalEntriesStore().load({
            params: {
                account: account
            }
        });
    }

});
