/* This file contains constructor functions for UI widgets and other objects
 * that are shared between ReeBill and XBill UIs. */

var accountStoreProxyConn = new Ext.data.Connection({
    url: 'http://' + location.host + '/reebill/retrieve_account_status',
});
accountStoreProxyConn.autoAbort = true;
var accountReader = new Ext.data.JsonReader({
    // metadata configuration options:
    // there is no concept of an id property because the records do not have identity other than being child charge nodes of a charges parent
    //idProperty: 'id',
    root: 'rows',

    // the fields config option will internally create an Ext.data.Record
    // constructor that provides mapping for reading the record data objects
    fields: [
        // map Record's field to json object's key of same name
        {name: 'account', mapping: 'account'},
        {name: 'fullname', mapping: 'fullname'},
        {name: 'dayssince', mapping: 'dayssince'/*, type:sortType*/},
        {name: 'lastissuedate'},
        {name: 'lastevent'},
        {name: 'provisionable', mapping: 'provisionable'},
    ]
});
var accountStoreProxy = new Ext.data.HttpProxy(accountStoreProxyConn);
var accountStore = new Ext.data.JsonStore({
    proxy: accountStoreProxy,
    root: 'rows',
    totalProperty: 'results',
    remoteSort: true,
    paramNames: {start: 'start', limit: 'limit'},
    //sortInfo: {
        //field: defaultAccountSortField,
        //direction: defaultAccountSortDir,
    //},
    autoLoad: {params:{start: 0, limit: 30}},
    reader: accountReader,
    fields: [
        {name: 'account'},
        {name: 'codename'},
        {name: 'casualname'},
        {name: 'primusname'},
        {name: 'utilityserviceaddress'},
        {name: 'dayssince'},
        {name: 'lastevent'},
        {name: 'lastissuedate'},
        {name: 'provisionable'},
    ],
});


var accountGridColumnRenderer = function(value, metaData, record, rowIndex, colIndex, store) {
    // probably the right way to do this is to set metaData.css to a CSS class name, but setting metaData.attr works for me.
    // see documentation for "renderer" config option of Ext.grid.Column

    // show text for accounts that don't yet exist in billing in gray;
    // actual billing accounts are black
    //if (record.data.provisionable) {
        //metaData.attr = 'style="color:gray"';
    //} else {
        //metaData.attr = 'style="color:black"';
    //}
    if (record.data.provisionable) {
        metaData.css = 'account-grid-gray';
    } else {
        metaData.css = 'account-grid-black';
    }
    return value;
}


function CustomerAccountGrid(title, columnNames) {
    /* config objects for Ext.grid.Columns that can go in a grid of customer
     * account information. The grid inheriting from this constructor specifies
     * a list of names to choose which columns should be shown. */
    var standardColumns = {
        'account': {
            header: 'Account',
            sortable: true,
            dataIndex: 'account',
            renderer: accountGridColumnRenderer,
        },
        'codename': {
            header: 'Codename',
            sortable: true,
            dataIndex: 'codename',
            renderer: accountGridColumnRenderer,
        },
        'casualname': {
            header: 'Casual Name',
            sortable: true,
            dataIndex: 'casualname',
            renderer: accountGridColumnRenderer,
        },
        'primusname': {
            header: 'Primus Name',
            sortable: true,
            dataIndex: 'primusname',
            renderer: accountGridColumnRenderer,
        },
        'utilityserviceaddress': {
            header: 'Utility Service Address',
            sortable: true,
            dataIndex: 'utilityserviceaddress',
            renderer: accountGridColumnRenderer,
        },
        'lastissuedate': {
            header: 'Last Issued',
            sortable: true,
            dataIndex: 'lastissuedate',
            renderer: accountGridColumnRenderer,
        },
        'dayssince': {
            header: 'Days Since Utility Bill',
            sortable: true,
            dataIndex: 'dayssince',
            renderer: accountGridColumnRenderer,
        },
        'lastevent': {
            header: 'Last Event',
            sortable: false,
            dataIndex: 'lastevent',
            renderer: accountGridColumnRenderer,
            width: 350,
        }
    }

    this.title = title;

    var the_columns = [];
    for (var i = 0; i < columnNames.length; i++) {
        the_columns.push(standardColumns[columnNames[i]]);
    }
    this.colModel = new Ext.grid.ColumnModel({columns: the_columns});

    this.selModel = new Ext.grid.RowSelectionModel({singleSelect:true});

    this.store = accountStore;
    this.frame = true;
    this.collapsible = true;
};

CustomerAccountGrid.prototype = new Ext.grid.EditorGridPanel(
    /* the properties defined here apparently can't be defined by this. ... =
     * ... as above */

    {
        viewConfig: { forceFit: true, },

        bbar: new Ext.PagingToolbar({
            pageSize: 30,
            store: accountStore,
            displayInfo: true,
            displayMsg: 'Displaying {0} - {1} of {2}',
            emptyMsg: "No statuses to display",
        }),
})

