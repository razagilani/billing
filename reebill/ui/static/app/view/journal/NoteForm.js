Ext.define('ReeBill.view.NoteForm', {
    extend: 'Ext.form.Panel',

    title: 'Add a Note',

    alias: 'widget.noteForm',    

    bodyPadding: 15,
    
    defaults: {
        anchor: '100%'
    },

    items: [{
        xtype: 'textarea',
        name: 'entry',
        height: 150,
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