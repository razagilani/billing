Ext.define('DocumentTools.controller.DocumentViewer', {
    extend: 'Ext.app.Controller',

    init: function() {
        this.application.on({
            scope: this,
            beforeimageload: this.loadImage
        });
    },

    /**
     * Load the image in the document viewer.
     */
    loadImage: function(imageRec) {
        if (!imageRec)
            return;

        var scope = this;

        if (this.image)
            this.image.destroy();

        this.image = Ext.create('Ext.Img', {
            id: 'documentImage',
            src: imageRec.get('path'),
            renderTo: 'imageContainer',
            listeners: {
                load: {
                    element: 'el',
                    fn: function() {
                        scope.application.fireEvent('imageload', imageRec);
                    }
                }
            }
        });
    }

});
