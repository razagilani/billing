Ext.define('DocumentTools.controller.Tags', {
    extend: 'Ext.app.Controller',
    
    views: [
        'Tags'
    ],
    
    refs: [{
        ref: 'tagsGrid',
        selector: 'grid[id=tagsGrid]'
    }],
    
    init: function() {
        this.application.on({
            scope: this
        });
        
        this.control({
            'grid[id=tagsGrid]': {
                cellclick: function() {}
            }
        });
    }

});
