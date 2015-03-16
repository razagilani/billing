/**
 * Created by thoffmann on 9/9/14.
 */
var utils = function() {
    var makeServerExceptionWindow = function(statusCode, statusText, content){
        var win = Ext.create('Ext.window.Window', {
            modal: true,
            autoScroll: true,
            width: 850,
            maxHeight: 650,
            cls: 'messageBoxOverflow',
            title: "Server error - " + statusCode + " - " + statusText,
            layout     : {
                type  : 'hbox',
                align : 'stetch'
            },
            items      : [
                {
                    html : content,
                    flex : 1
                }
            ]
        });
        win.show();
        win.center();
    };

    var makeProxyExceptionHandler = function(storeName) {
        /* Creates a function which rejects changes in the store storeName and
         shows and appropriate error message box */
        return function (proxy, response, operation) {
            var statusText, responseText;
            if (response.status === 0) {
                statusText = 'Connection Refused';
                responseText = 'The server has refused the connection!';
            } else {
                statusText = response.statusText;
                responseText = response.responseText;
            }

            Ext.getStore(storeName).rejectChanges();
            makeServerExceptionWindow(response.status, statusText, responseText)
        }
    };

    return {
        makeProxyExceptionHandler: makeProxyExceptionHandler,
        makeServerExceptionWindow: makeServerExceptionWindow
    };
}();
