Ext.define('DocumentTools.controller.Exporter', {
    extend: 'Ext.app.Controller',

    stores: [
        'Images',
        'Regions',
        'Tags'
    ],
        
    init: function() {
        this.application.on({
            scope: this,
            imageload: this.saveImage 
        });
        
        this.control({
            'button[action=exportJSON]': {
                click: this.exportJSON
            }
        });
    },

    /**
     * Export everything as JSON.
     */
    exportJSON: function() {
        var regionsStore = this.getRegionsStore(),
            tagsStore = this.getTagsStore()
            currentImage = this.currentImage;

        if (!currentImage)
            return;

        var json = {};
        json.id = currentImage.get('id');
        json.name = currentImage.get('name');
        json.path = currentImage.get('path');

        json.regions = [];
        regionsStore.each(function(region) {
            json.regions.push({
                id: region.get('id'),
                name: region.get('name'),
                type: region.get('type'),
                width: region.get('width'),
                height: region.get('height'),
                x: region.get('x'),
                y: region.get('y'),
                hidden: region.get('hidden')
            });
        });

        json.tags = [];
        tagsStore.each(function(tag) {
            json.tags.push({
                id: tag.get('id'),
                tag: tag.get('tag')
            });
        });

        Ext.create('Ext.Window', {
            title: 'JSON',
            width: 700,
            height: 600,
            items: [{
                xtype: 'form',
                bodyPadding: 10,
                items: [{
                    xtype: 'textareafield',
                    value: JSON.stringify(json, null, '\t'),
                    anchor: '100%',
                    height: 550
                }]             
            }]
        }).show();
    },

    /**
     * Save the selected image.
     */
    saveImage: function(image) {
        this.currentImage = image;
    }

});
