Ext.define('ReeBill.store.Preferences', {
    extend: 'Ext.data.Store',

    model: 'ReeBill.model.Preference',

    autoLoad: true,
    autoSync: true,

	proxy: {
		type: 'rest',

        simpleSortMode: true,

        pageParam: false,
        startParam: false,
        limitParam: false,
        sortParam: false,
        groupParam: false,

        url: 'http://'+window.location.host+'/reebill/preferences',
		reader: {
			type: 'json',
			root: 'rows',
			totalProperty: 'results'
		},

        listeners:{
            exception: function (proxy, response, operation) {
                Ext.getStore('Preferences').rejectChanges();
                Ext.MessageBox.show({
                    title: "Server error - " + response.status + " - " + response.statusText,
                    msg:  response.responseText,
                    icon: Ext.MessageBox.ERROR,
                    buttons: Ext.Msg.OK,
                    cls: 'messageBoxOverflow'
                });
            },
            scope: this
        },

	},

    /**
     * Checks if Preference with key pref exists and retrieves it if it does
     * If it doesn't, this function creates one and returns it
     */
    getOrCreate: function(pref, val){
        var result = this.find('key', pref);
        if(result === -1){
            result = this.add({key: pref, value: val});
        }else{
            result = this.getAt(result);
        }
        return result;
    },

    /**
     * Sets preference pref to val. If it doesn't exist, preferenece pref is
     * created first
     */
    setOrCreate: function(pref, val){
        var model = this.find('key', pref);
        if(model === -1){
            var result = this.add({key: pref, value: val});
        }else{
            model = this.getAt(model);
            model.set('value', val);
            var result = model;
        }
        return model;
    },

    sorters: [{
        property: 'key',
        direction: 'DESC'
    }]
});