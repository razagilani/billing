Ext.define('DocumentTools.controller.Regions', {
    extend: 'Ext.app.Controller',
    
    views: [
        'Regions'
    ],

    stores: [
        'Regions'
    ],
    
    refs: [{
        ref: 'regionWindow',
        selector: 'window[name=regionWindow]'
    },{
        ref: 'regionsGrid',
        selector: 'grid[id=regionsGrid]'
    },{
        ref: 'colorField',
        selector: 'colorfield[name=color]'
    },{
        ref: 'regionsGrid',
        selector: 'grid[id=regionsGrid]'
    },{
        ref: 'regionForm',
        selector: 'form[id=regionForm]'
    },{
        ref: 'sliderField',
        selector: 'sliderfield[name=opacity]'
    },{
        ref: 'viewerComponent',
        selector: '[id=viewerComponent]'
    }],
    
    init: function() {
        this.application.on({
            scope: this,
            imageload: this.initViewer 
        });
        
        this.control({
            'grid[id=regionsGrid]': {
                cellclick: function() {}
            },
            'button[action=addRegion]': {
                click: this.handleAddRegion
            },
            'button[action=editRegion]': {
                click: this.handleEditRegion
            },
            'button[action=deleteRegion]': {
                click: this.handleDeleteRegion
            },
            'button[action=toggleShow]': {
                click: this.handleToggleShow
            },
            'button[action=saveRegion]': {
                click: this.handleSaveRegion
            },
            'button[action=cancelRegion]': {
                click: function() {
                    this.getRegionWindow().close();
                }
            },
            'window[name=regionWindow]': {
                close: this.handleRegionWindowClose
            },
            'button[action=zoomIn]': {
                click: this.zoomIn
            },
            'button[action=zoomOut]': {
                click: this.zoomOut
            },
            'sliderfield[name=opacity]': {
                change: this.handleOpacityChange
            },
            '[id=viewerComponent]': {
                resize: this.handleResize
            }
        });

        this.getRegionsStore().on({
            datachanged: this.markRegions,
            scope: this
        });

    },

    /**
     * Load the regions store based on the selected image.
     */ 
    loadRegions: function(imageRec) {
        if (!imageRec)
            return;

        this.currentImage = imageRec;

        var store = this.getRegionsStore();

        store.load({id: imageRec.get('id')});
    },

    /**
     * Initialize the viewer based on browser size.
     */
    initViewer: function(imageRec) {
        var componentWidth = this.getViewerComponent().getWidth();
        var componentHeight = this.getViewerComponent().getHeight();
        
        this.imageWidth = $('#documentImage').width();
        this.imageHeight = $('#documentImage').height();

        this.currentZoom = componentWidth / this.imageWidth;

        if ((this.currentZoom * this.imageHeight) > componentHeight)
            this.currentZoom = componentHeight / this.imageHeight;

        this.originalWidth = this.currentZoom * this.imageWidth;
        this.originalHeight = this.currentZoom * this.imageHeight;

        $('#documentImage').width(this.originalWidth);
        $('#documentImage').height(this.originalHeight);

        $("#imageTool").css({
            'left': $("#imageTool").data('originalLeft'),
            'top': $("#imageTool").data('origionalTop')
        });

        this.loadRegions(imageRec);
    },

    /**
     * Handle a resize of the window.
     */
    handleResize: function() {
        var componentWidth = this.getViewerComponent().getWidth();
        var componentHeight = this.getViewerComponent().getHeight();

        this.currentZoom = componentWidth / this.imageWidth;

        if ((this.currentZoom * this.imageHeight) > componentHeight)
            this.currentZoom = componentHeight / this.imageHeight;

        this.originalWidth = this.currentZoom * this.imageWidth;
        this.originalHeight = this.currentZoom * this.imageHeight;

        $('#documentImage').width(this.originalWidth);
        $('#documentImage').height(this.originalHeight);

        this.markRegions();
    },

    /**
     * Add a new region to the image. 
     */
    handleAddRegion: function() {
        if (!this.currentImage)
            return;

        this.getRegionWindow().show();
        this.handleOpacityChange();
    },

    /**
     * Handle edit region button.
     */
    handleEditRegion: function() {
        if (!this.currentImage)
            return;

        var selections = this.getRegionsGrid().getSelectionModel().getSelection();
        if (!selections.length)
            return;

        this.loadForm(selections[0]);

        this.getRegionWindow().show();
        this.handleOpacityChange();
    },

    /**
     * Delete the selected region. 
     */
    handleDeleteRegion: function() {
        var selections = this.getRegionsGrid().getSelectionModel().getSelection();

        if (selections.length)
            this.deleteRegion(selections[0]);
    },

    /**
     * Handle the toggle show button.
     */
    handleToggleShow: function() {
        var selections = this.getRegionsGrid().getSelectionModel().getSelection();

        if (selections.length) {
            var rec = selections[0];

            rec.set('hidden', !rec.get('hidden'));

            this.saveRegion(rec);
        }
    },

    /**
     * Mark all the regions currently in the store. 
     */
    markRegions: function() {
        var scope = this;
        var store = this.getRegionsStore();
        var currentZoom = this.currentZoom;

        $('.region').remove();

        store.each(function(rec) {
            if (rec.get('hidden'))
                return;

            var newRegion = $('<div class="region" title="' + (rec.get('description') || '') + '" id="region_' + rec.get('id') + '"><b>' + rec.get('name') + '</b></div>');

            $('#imageContainer').append(newRegion);
            
            $(newRegion)
                .css('position', 'absolute')
                .css('width', rec.get('width') * currentZoom)
                .css('height', rec.get('height') * currentZoom)
                .css('top', rec.get('y') * currentZoom)
                .css('left', rec.get('x') * currentZoom)
                .css('opacity', rec.get('opacity'))
                .css('background-color', '#' + rec.get('color'))
                .draggable({
                    containment: "parent",
                    stop: function() {
                        scope.updateLocation.apply(scope, arguments)
                    }

                })
                .resizable({
                    stop: function() {
                        scope.updateSize.apply(scope, arguments)
                    }
                });
        });
    },

    /**
     * Load the region form.
     * @param rec The record to load.
     */
    loadForm: function(rec) {
        var form = this.getRegionForm(),
            name = form.down('[name=name]'),
            description = form.down('[name=description]'),
            color = form.down('[name=color]'),
            opacity = form.down('[name=opacity]'),
            id = form.down('[name=id]');

        name.setValue(rec.get('name'));
        color.setValue(rec.get('color'));
        description.setValue(rec.get('description'));
        opacity.setValue(rec.get('opacity') * 100);
        id.setValue(rec.get('id'));
    },

    /** 
     * Handle the save region click.
     */
    handleSaveRegion: function() {
        var form = this.getRegionForm(),
            name = form.down('[name=name]').getValue(),
            description = form.down('[name=description]').getValue(),
            color = form.down('[name=color]').getValue(),
            opacity = form.down('[name=opacity]').getValue(),
            id = form.down('[name=id]').getValue(),
            store = this.getRegionsStore();

        if (!form.isValid()) {
            Ext.Msg.alert('Missing Data', 'Please enter all required fields.');
            return;
        }

        var rec = store.findRecord('id', id);

        if (!rec) {
            rec = new DocumentTools.model.Region();
        }

        rec.set('image_id', this.currentImage.get('id'));
        rec.set('name', name);
        rec.set('description', description);
        rec.set('color', color);
        rec.set('opacity', opacity / 100);

        this.saveRegion(rec);
    },

    /**
     * Make the AJAX request to store the region.
     */
    saveRegion: function(rec) {
        var store = this.getRegionsStore(),
            scope = this;

        Ext.Ajax.request({
            url: 'php/saveRegion.php',
            method: 'POST',          
            params: {
                id: rec.get('id'),
                image_id: rec.get('image_id'),
                name: rec.get('name'),
                description: rec.get('description'),
                color: rec.get('color'),
                opacity: rec.get('opacity'),
                x: rec.get('x'),
                y: rec.get('y'),
                height: rec.get('height'),
                width: rec.get('width'),
                hidden: rec.get('hidden')
            },
            success: function() {
                store.reload();

                scope.getRegionWindow().close();
            }
        });

    },

    /**
     * Make the AJAX request to delete the region.
     */
    deleteRegion: function(rec) {
        var store = this.getRegionsStore(),
            scope = this;

        Ext.Ajax.request({
            url: 'php/deleteRegion.php',
            method: 'POST',          
            params: {
                id: rec.get('id')
            },
            success: function() {
                store.reload();
            }
        });
    },

    /**
     * Handle the region window closing.
     */
    handleRegionWindowClose: function() {
        this.getRegionForm().getForm().reset();
    },

    /**
     * Handle changes to the opacity slider.
     */
    handleOpacityChange: function() {
        Ext.ux.ColorField.superclass.setFieldStyle.call(this.getColorField(), {
            'opacity': this.getSliderField().getValue() / 100
        });    
    },

    /**
     * Update the size of a region.
     */
    updateSize: function( event, ui ) {
        var domId = ui.helper.attr('id');
        var id = domId.substring(7);
        var rec = this.getRegionsStore().findRecord('id', id);

        if (!rec)
            return;

        var adj =  this.imageWidth / $('#documentImage').width();

        rec.set('width', Math.round(ui.size.width * adj));
        rec.set('height', Math.round(ui.size.height * adj));

        this.saveRegion(rec);
    },

    /**
     * Update the location of a region.
     */
    updateLocation: function( event, ui ) {
        var domId = ui.helper.attr('id'),
            id = domId.substring(7),
            rec = this.getRegionsStore().findRecord('id', id),
            offset = $('#imageContainer').offset();

        if (!rec)
            return;

        var adj =  this.imageWidth / $('#documentImage').width();

        rec.set('y', Math.round((ui.offset.top - offset.top) * adj));
        rec.set('x', Math.round((ui.offset.left - offset.left) * adj));

        this.saveRegion(rec);
    },

    /**
     * Zoom in on the document viewer.
     */ 
    zoomIn: function() {
        this.currentZoom = Math.min(this.currentZoom + .15, 1.6);

        this.zoom();
    },

    /**
     * Zoom out on the document viewer.
     */ 
    zoomOut: function() {
        this.currentZoom = Math.max(this.currentZoom - .15, .4);

        this.zoom();
    },

    /**
     * Do the actual zooming.
     */
    zoom: function() {
        $('#documentImage').width(this.currentZoom * this.imageWidth);
        $('#documentImage').height(this.currentZoom * this.imageHeight);

        this.markRegions();
    }
});
