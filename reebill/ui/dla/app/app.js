Ext.application({
    name: 'DocumentTools',
    autoCreateViewport: true,
    
    controllers: ['DocumentViewer', 'Exporter', 'Images', 'Regions', 'Tags'],
    
    stores: ['Images', 'Regions', 'Tags'],
    models: ['Image', 'Region', 'Tag'],
    
    launch: function() {
        $('#imageTool').draggable();

        $("#imageTool").data({
		    'originalLeft': $("#imageTool").css('left'),
		    'origionalTop': $("#imageTool").css('top')
		});
    }

});