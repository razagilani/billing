Ext.define('DocumentTools.controller.Tags', {
    extend: 'Ext.app.Controller',
    
    views: [
        'Tags'
    ],
    
    refs: [{
        ref: 'tagsGrid',
        selector: 'grid[id=tagsGrid]'
    },{
        ref: 'tagWindow',
        selector: 'window[name=tagWindow]'
    },{
        ref: 'tagForm',
        selector: 'form[id=tagForm]'
    }],
    
    stores: [
        'Tags'
    ],
    
    init: function() {
        this.application.on({
            scope: this,
            imageload: this.loadTags
        });
        
        this.control({
            'grid[id=tagsGrid]': {
                cellclick: function() {}
            },
            'button[action=addTag]': {
                click: this.handleAddTag
            },
            'button[action=editTag]': {
                click: this.handleEditTag
            },
            'button[action=deleteTag]': {
                click: this.handleDeleteTag
            },
            'button[action=saveTag]': {
                click: this.handleSaveTag
            },
            'button[action=cancelTag]': {
                click: function() {
                    this.getTagWindow().close();
                }
            },
            'window[name=tagWindow]': {
                close: this.handleTagWindowClose
            } 
        });
    },

    /**
     * Load the tags store based on the selected image.
     */ 
    loadTags: function(imageRec) {
        if (!imageRec)
            return;

        this.currentImage = imageRec;

        var store = this.getTagsStore();

        store.load({id: imageRec.get('id')});
    },

    /**
     * Add a new tag. 
     */
    handleAddTag: function() {
        if (!this.currentImage)
            return;

        this.getTagWindow().show();
    },

    /**
     * Handle edit tag button.
     */
    handleEditTag: function() {
        if (!this.currentImage)
            return;

        var selections = this.getTagsGrid().getSelectionModel().getSelection();
        if (!selections.length)
            return;

        this.loadForm(selections[0]);

        this.getTagWindow().show();
    },

    /**
     * Delete the selected tag. 
     */
    handleDeleteTag: function() {
        var selections = this.getTagsGrid().getSelectionModel().getSelection();

        if (selections.length)
            this.deleteTag(selections[0]);
    },

    /**
     * Load the tag form.
     * @param rec The record to load.
     */
    loadForm: function(rec) {
        var form = this.getTagForm(),
            tag = form.down('[name=tag]'),
            id = form.down('[name=id]');

        tag.setValue(rec.get('tag'));
        id.setValue(rec.get('id'));
    },

    /** 
     * Handle the save tag button.
     */
    handleSaveTag: function() {
        var form = this.getTagForm(),
            id = form.down('[name=id]').getValue(),
            tag = form.down('[name=tag]').getValue(),
            image_id = this.currentImage.get('id'),
            store = this.getTagsStore(),
            scope = this;

        if (!form.isValid()) {
            Ext.Msg.alert('Missing Data', 'Please enter all required fields.');
            return;
        }

        var rec = store.findRecord('id', id);

        if (!rec) {
            rec = new DocumentTools.model.Tag();
        }

        rec.set('image_id', image_id);
        rec.set('tag', tag);

        this.saveTag(rec);
    },

    /** 
     * Make the AJAX request to store the tag.
     */
    saveTag: function(rec) {
        var store = this.getTagsStore(),
            scope = this;

        Ext.Ajax.request({
            url: '../reebill/dlasavetag',
            method: 'POST',          
            params: {
                id: rec.get('id'),
                image_id: rec.get('image_id'),
                tag: rec.get('tag')
            },
            success: function() {
                store.reload();

                scope.getTagWindow().close();
            }
        });
    },

    /**
     * Handle the tag window closing.
     */
    handleTagWindowClose: function() {
        this.getTagForm().getForm().reset();
    },

    /**
     * Make the AJAX request to delete the tag.
     */
    deleteTag: function(rec) {
        var store = this.getTagsStore(),
            scope = this;

        Ext.Ajax.request({
            url: 'php/deleteTag.php',
            method: 'POST',          
            params: {
                id: rec.get('id')
            },
            success: function() {
                store.reload();
            }
        });

    },

});
