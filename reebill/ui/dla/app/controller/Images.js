Ext.define('DocumentTools.controller.Images', {
    extend: 'Ext.app.Controller',

    stores: [
        'Images'
    ],
    
    refs: [{
        ref: 'imageForm',
        selector: 'form[id=imageForm]'
    },{
        ref: 'newImageForm',
        selector: 'form[id=newImageForm]'
    },{
        ref: 'imagesWindow',
        selector: 'window[name=imagesWindow]'
    },{
        ref: 'newImageWindow',
        selector: 'window[name=newImageWindow]'
    },{
        ref: 'imageCombo',
        selector: 'combo[name=image]'        
    }],
    
    init: function() {
        this.application.on({
            scope: this
        });
        
        this.control({
            'button[action=showImages]': {
                click: this.showImages
            },
            'button[action=addImage]': {
                click: this.addImage
            },
            'button[action=deleteImage]': {
                click: this.deleteImage
            },
            'button[action=saveNewImage]': {
                click: this.saveNewImage
            },
            'button[action=closeImages]': {
                click: this.closeImages
            },
            'button[action=cancelAddImage]': {
                click: this.cancelAddImage
            },
            'button[action=loadImage]': {
                click: this.loadImage
            }
        });

        this.getImageCombo().bindStore(this.getImagesStore());
    },

    /**
     * Show the images window.
     */
    showImages: function() {
        this.getImagesWindow().show();
    },

    /**
     * Show the add image window.
     */
    addImage: function() {
        this.getNewImageWindow().show();
    },

    /**
     * Load the selected image.
     */
    loadImage: function() {
        var combo = this.getImageCombo(),
            imageId = combo.getValue(),
            store = this.getImagesStore();

        if (!imageId)
            return;

        this.closeImages();

        var imageRec = store.findRecord('id', imageId);

        this.application.fireEvent('beforeimageload', imageRec);
    },

    /**
     * Save the new image.
     */
    saveNewImage: function() {
        var form = this.getNewImageForm(),
            name = form.down('[name=name]').getValue(),
            path = form.down('[name=path]').getValue(),
            store = this.getImagesStore(),
            newImageWindow = this.getNewImageWindow();

        Ext.Ajax.request({
            url: 'php/addImage.php',
            method: 'POST',          
            params: {
                name: name,
                path: path
            },
            success: function() {
                form.getForm().reset();
                store.reload();
                newImageWindow.hide();
            }
        });
    },


    /**
     * Make the AJAX request to delete the image.
     */
    deleteImage: function() {
        var form = this.getImageForm(),
            combo = this.getImageCombo(),
            store = this.getImagesStore(),
            val = combo.getValue(),
            scope = this;

        Ext.Ajax.request({
            url: 'php/deleteImage.php',
            method: 'POST',          
            params: {
                id: val
            },
            success: function() {
                form.getForm().reset();
                store.reload();
            }
        });
    },

    /**
     * Hide the images window.
     */
    closeImages: function() {
        this.getImagesWindow().hide();
    },

    /**
     * Hide the add image window.
     */
    cancelAddImage: function() {
        this.getNewImageWindow().hide();
    }

});
