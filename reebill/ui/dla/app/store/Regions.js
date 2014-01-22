Ext.define('DocumentTools.store.Regions', {
    extend: 'Ext.data.Store',
    
    model: 'DocumentTools.model.Region',
    data: [{
    	id: '1',
        name: 'Tree',
        description: 'Big tree in the middle.',
    	x: 200,
    	y: 15,
    	width: 281,
    	height: 421,
    	color: '3366FF',
    	opacity: 0.65
    },{
    	id: '2',
    	name: 'Bridge',
        description: 'Wooden bridge over the water.',
    	x: 795,
    	y: 379,
    	width: 271,
    	height: 154,
    	color: 'FFFF00',
    	opacity: 0.65    	
    },{
    	id: '3',
        name: 'Steps',
    	description: 'Steps leading to another bridge.',
    	x: 687,
    	y: 323,
    	width: 100,
    	height: 100,
    	color: 'FF00FF',
    	opacity: 0.65    	
    },{
    	id: '4',
    	name: 'Water',
        description: 'Shallow water with rocks.',
    	x: 454,
    	y: 410,
    	width: 240,
    	height: 150,
    	color: 'FF0000',
    	opacity: 0.65    	
    }]
});