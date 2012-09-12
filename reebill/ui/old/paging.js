Ext.onReady(function(){
    // data store
    var store = new Ext.data.JsonStore({
        root: 'rows', // name of the list of rows in the JSON packet returned by the server
        totalProperty: 'results', // part of JSON packet that says how many rows there are
        pageSize: 25,
        paramNames: {start: 'start', limit: 'limit'},
        autoLoad: {params:{start: 0, limit: 25}},
        
        fields: [
            {name: 'account'},
            {name: 'period_start', type: 'date'},
            {name: 'period_end', type: 'date'},
        ],
        
        url: 'http://localhost:8080/getbills'
    });
    
    // paging GridPanel
    var grid = new Ext.grid.GridPanel({
        width:700,
        height:500,
        title:'ExtJS.com - Browse Forums',
        store: store,
        trackMouseOver:false,
        disableSelection:true,
        //loadMask: true,

        // grid columns
        columns:[{
            header: 'Account',
            dataIndex: 'account',
        width:100,
        },{
            header: 'Start Date',
            dataIndex: 'period_start',
            width: 300,
        },{
            header: 'End Date',
            dataIndex: 'period_end',
            width: 300,
        }],
        
        // paging bar on the bottom
        bbar: new Ext.PagingToolbar({
            pageSize: 25,
            store: store,
            displayInfo: true,
            displayMsg: 'Displaying topics {0} - {1} of {2}',
            emptyMsg: "No topics to display",
            items:[
                '-', {
                pressed: true,
                enableToggle:true,
                text: 'Show Preview',
                cls: 'x-btn-text-icon details',
                toggleHandler: function(btn, pressed){
                    var view = grid.getView();
                    //view.showPreview = pressed;
                    view.refresh();
                }
            }]
        })
    });

    // render it
    grid.render('topic-grid');
});
