Ext.application({
    name: 'DocumentTools',
    autoCreateViewport: true,
    
    controllers: ['Tags', 'Regions'],
    
    stores: ['Tags', 'Regions'],
    models: ['Tag', 'Region'],
    
    launch: function() {
        $('#imageTool').draggable();
    }

});