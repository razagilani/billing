Ext.define('DocumentTools.store.Tags', {
    extend: 'Ext.data.Store',
    
    model: 'DocumentTools.model.Tag',
    data : [
         {id: '1', tag: 'Tag 1'},
         {id: '2', tag: 'Tag 2'},
         {id: '3', tag: 'Tag 3'}
     ]
});