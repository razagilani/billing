Ext.define('ReeBill.view.journal.NoteForm', {
    extend: 'Ext.form.Panel',

    title: 'Add a Note',

    alias: 'widget.noteForm',    

    componentCls: 'noteform-noborder',

    height: 150,

    items: [{
        xtype: 'textarea',
        name: 'entry',
        height: '100%',
        width: '100%',
        hideLabel: true,
        allowBlank: false
    }],
    
    dockedItems: [{
        dock: 'bottom',
        xtype: 'toolbar',
        items: ['->',{        
            xtype: 'button',
            text: 'Reset',
            action: 'handleNoteReset'
        },{        
            xtype: 'button',
            text: 'Submit',
            action: 'handleNoteSubmit'
        }]
    }]

});
