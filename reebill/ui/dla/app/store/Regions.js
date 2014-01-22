Ext.define('DocumentTools.store.Regions', {
    extend: 'Ext.data.Store',
    
    model: 'DocumentTools.model.Region',
    data: [{
    	id: '1',
        name: 'Summary',
        description: 'Summary of bill information',
    	x: 35,
    	y: 130,
    	width: 380,
    	height: 220,
    	color: '3366FF',
    	opacity: 0.65
    },{
    	id: '2',
    	name: 'Account #',
        description: 'Account # of recipient',
    	x: 48,
    	y: 775,
    	width: 280,
    	height: 40,
    	color: 'FFFF00',
    	opacity: 0.65    	
    },{
    	id: '3',
        name: 'Ammount Due',
    	description: 'Ammount owed to utility',
    	x: 475,
    	y: 810,
    	width: 150,
    	height: 60,
    	color: 'FF00FF',
    	opacity: 0.65    	
    },{
    	id: '4',
    	name: 'Electric Charges',
        description: 'Summary of charges for electric service',
    	x: 35,
    	y: 1290,
    	width: 370,
    	height: 200,
    	color: 'FF0000',
    	opacity: 0.65    	
    }]
});
