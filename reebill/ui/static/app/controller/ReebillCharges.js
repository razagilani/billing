Ext.define('ReeBill.controller.ReebillCharges', {
    extend: 'Ext.app.Controller',

    stores: [
        'ReebillCharges', 'ReeBillVersions'
    ],

    views: ['reebillcharges.ReebillCharges'],
    
    refs: [{
        ref: 'accountsGrid',
        selector: 'grid[id=accountsGrid]'
    },{
        ref: 'reebillChargesTab',
        selector: 'panel[name=reebillChargesTab]'
    },{
        ref: 'reebillsGrid',
        selector: 'grid[id=reebillsGrid]'
    },{
        ref: 'reeBillVersions',
        selector: 'combo[name=reeBillChargesVersions]'
    }],

    init: function() {
        this.application.on({
            scope: this
        });
        
        this.control({
            'panel[name=reebillChargesTab]': {
                activate: this.handleActivate
            },
            'combo[name=reeBillChargesVersions]': {
                select: this.loadCharges
            }
        });

        this.getReeBillVersionsStore().on({
            load: function(){
                var store = this.getReeBillVersionsStore();
                var combo = this.getReeBillVersions();
                // Select the first element
                combo.select(store.getAt(0));
                this.loadCharges();
            },
            scope: this
        });
    },

    /**
     * Handle the panel being activated.
     */
    handleActivate: function() {
         var selections = this.getReebillsGrid().getSelectionModel().getSelection();
         if (!selections.length)
             return;
         var selected = selections[0];
         var account = selected.get('account');
         var sequence = selected.get('sequence');

         // Set store parameters for ReebillVersions
         var versionStore = this.getReeBillVersionsStore();
         versionStore.getProxy().extraParams = {
             account: account,
             sequence: sequence
         };
         versionStore.reload();
    },

    /**
     * Handle the panel being activated.
     */
    loadCharges: function() {
        var combo = this.getReeBillVersions();
        var versionStore = this.getReeBillVersionsStore();
        var version = combo.getValue();
        var store = this.getReebillChargesStore();

        var selected = versionStore.getAt(versionStore.find('version', version));

        store.getProxy().setExtraParam('reebill_id', selected.get('id'));
        store.reload();
    },

});
