Ext.define('DocumentTools.model.Region', {
    extend: 'Ext.data.Model',
    fields: [
        {name: 'id',  type: 'string'},
        {name: 'name',  type: 'string'},
        {name: 'description',  type: 'string'},
        {name: 'x',   type: 'float', defaultValue: 50},
        {name: 'y',   type: 'float', defaultValue: 50},
        {name: 'width',   type: 'float', defaultValue: 100},
        {name: 'height',   type: 'float', defaultValue: 100},
        {name: 'color',  type: 'string'},
        {name: 'opacity',   type: 'float'}
    ]
});