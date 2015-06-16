Ext.define('ReeBill.controller.Journal', {
    extend: 'Ext.app.Controller',

    stores: [
        'JournalEntries'
    ],

    views: [
      'journal.NoteForm', 'journal.JournalEntries'
    ],
    
    refs: [{
        ref: 'noteForm',
        selector: 'noteForm'
    },{
        ref: 'accountsGrid',
        selector: 'grid[id=accountsGrid]'
    },{
        ref: 'reebillsGrid',
        selector: 'grid[id=reebillsGrid]'
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

        this.getJournalEntriesStore().on({
            add: this.handleNoteReset,
            scope: this
        });
    },

    /**
     * Handle the submit button being clicked.
     */
    handleSubmit: function() {
        var me = this;
        var selectedAccount = this.getAccountsGrid().getSelectionModel().getSelection()[0];
        var selectedReebill = this.getReebillsGrid().getSelectionModel().getSelection()[0];
        var content = this.getNoteForm().getForm().getFields().getAt(0).getValue();
        var account = null;
        var sequence = null;

        if(selectedAccount !== undefined){
            account = selectedAccount.get('account');
        }
        if(selectedReebill !== undefined){
            sequence = selectedReebill.get('sequence');
        }

        var store = this.getJournalEntriesStore();
        store.add({
            account: account,
            sequence: sequence,
            msg: content
        })
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
        var store = this.getJournalEntriesStore();

        if (selectedAccount.length) {
            account = selectedAccount[0].get('account');
        }

        var title = account ? 'Journal Entries for Account ' + account : 'Journal Entries';
        this.getJournalEntriesGrid().setTitle(title);

        this.getNoteForm().setDisabled(!selectedAccount.length);

        store.getProxy().setExtraParam('account', account);
        store.reload();
    }

});
