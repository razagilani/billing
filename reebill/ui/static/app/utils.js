/**
 * Created by thoffmann on 9/9/14.
 */
var utils = function() {
    var makeProxyExceptionHandler = function(storeName) {
        /* Creates a function which rejects changes in the store storeName and
         shows and appropriate error message box */
        return function (proxy, response, operation) {
            if (response.status === 0) {
                var statusText = 'Connection Refused';
                var responseText = 'The server has refused the connection!';
                var cls = ''
            } else {
                var statusText = response.statusText;
                var responseText = response.responseText;
                var cls = 'messageBoxOverflow'
            }

            Ext.getStore(storeName).rejectChanges();
            var win = Ext.create('Ext.window.Window', {
                modal: true,
                autoScroll: true,
                width: 850,
                maxHeight: 650,
                cls: 'messageBoxOverflow',
                title: "Server error - " + response.status + " - " + statusText,
                layout     : {
                    type  : 'hbox',
                    align : 'stetch'
                },
                items      : [
                    {
                        html : response.responseText,
                        flex : 1
                    }
                ],
                bbar: [
                    '->', {
                        xtype: 'button',
                        text: 'Close',
                        listeners:{
                            click: function(){
                                win.close();
                            }
                        }
                    }, '->'
                ]
            });
            win.show();
            win.center();
        }
    };

    return {makeProxyExceptionHandler: makeProxyExceptionHandler};
}();
