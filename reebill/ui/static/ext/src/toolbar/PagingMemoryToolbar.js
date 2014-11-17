Ext.define('Ext.toolbar.PagingMemoryToolbar', {

    extend: 'Ext.toolbar.Paging',
    alias: 'widget.pagingmemorytoolbar',

    doRefresh: function(){
        var store = Ext.getStore(this.refreshStore);
        store.loadPage(1);
    }
});

