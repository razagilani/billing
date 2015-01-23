Ext.define('ReeBill.controller.UtilityBills', {
    extend: 'Ext.app.Controller',

    stores: [
        'UtilityBills',
        'ReeBillVersions',
        'RateClasses',
        'Suppliers',
        'Utilities',
        'Services'
    ],

    views: [
        'utilitybills.UtilityBills',
        'utilitybills.UploadUtilityBill'
    ],
    
    refs: [{
        ref: 'uploadUtilityBillForm',
        selector: 'uploadUtilityBill'
    },{
        ref: 'accountsGrid',
        selector: 'grid[id=accountsGrid]'
    }, {
        ref: 'utilityBillsGrid',
        selector: 'grid[id=utilityBillsGrid]'
    },{
        ref: 'accountLabel',
        selector: '[id=utilbillAccountLabel]'
    },{
        ref: 'utilbillCompute',
        selector: '[action=utilbillCompute]'
    },{
        ref: 'utilbillRemove',
        selector: '[action=utilbillRemove]'
    },{
        ref: 'utilbillToggleProcessed',
        selector: '[action=utilbillToggleProcessed]'
    }],    
    
    init: function() {
        this.application.on({
            scope: this
        });
        
        this.control({
            'grid[id=utilityBillsGrid]': {
                selectionchange: this.handleRowSelect
            },
            'panel[name=utilityBillsTab]': {
                activate: this.handleActivate
            },
            '[action=utilbillPrevious]': {
                click: function() {
                    this.currentAccountId--;
                    this.updateCurrentAccountId();
                    this.getUtilityBillsStore().reload();
                }
            },
            '[action=utilbillNext]': {
                click: function() {
                    this.currentAccountId++;
                    this.updateCurrentAccountId();
                    this.getUtilityBillsStore().reload();
                }
            },
            '[action=resetUploadUtilityBillForm]': {
                click: this.handleReset
            },
            '[action=submitUploadUtilityBillForm]': {
                click: this.handleSubmit
            },
            '[action=utilbillCompute]': {
                click: this.handleCompute
            },
            '[action=utilbillRemove]': {
                click: this.handleDelete
            },
            '[action=utilbillToggleProcessed]': {
                click: this.handleToggleProcessed
            },
            '#utility_combo':{
                select: this.handleUtilityComboChanged,
                focus: this.handleUtilityComboFocus
            },
            '#rate_class_combo': {
                expand: this.handleRateClassExpand
            }
        });

        this.getUtilityBillsStore().on({
            beforeload: function(store){
                var grid = this.getUtilityBillsGrid();
                grid.setLoading(true);
            },
            load: function(store) {
                var grid = this.getUtilityBillsGrid();
                grid.setLoading(false);
            },
            scope: this
        });
    },

    /**
     * Handle the row selection.
     */
    handleRowSelect: function(combo, recs) {
        var hasSelections = recs.length > 0;
        var selected = this.getUtilityBillsGrid().getSelectionModel().getSelection()[0];
        if (selected != null) {
            var processed = selected.get('processed')
            //this.getUtilbillCompute().setDisabled(!hasSelections || selected.get('processed'));
            //this.getUtilbillToggleProcessed().setDisabled(!hasSelections);

            //this.getUtilbillRemove().setDisabled(!hasSelections || processed);
            //var utility = selected.data.utility;
            //rate_class_store = Ext.getStore("RateClasses");
            //rate_class_store.clearFilter(true);
            //rate_class_store.filter('utility_id', utility.id);

            var chargesStore = Ext.getStore("Charges");
            var proxy = chargesStore.getProxy();
            var selected = this.getUtilityBillsGrid().getSelectionModel().getSelection()[0];
            proxy.extraParams = {utilbill_id: selected.get('id')};
            chargesStore.reload();
        } else {
            //this.getUtilbillCompute().setDisabled(true);
            //this.getUtilbillToggleProcessed().setDisabled(!hasSelections);
            //this.getUtilbillRemove().setDisabled(!hasSelections);
        }
    },

    /**
     * Handle the panel being activated.
     */
    handleActivate: function() {
        this.currentAccountId = 1;
        //this.getAccountLabel().setText(this.currentAccountId);
        this.updateCurrentAccountId();

        var store = this.getUtilityBillsStore();

        var selectedBill = this.getUtilityBillsGrid().getSelectionModel().getSelection();
        var selectedNode;
        if (!selectedBill || !selectedBill.length) {
            selectedNode = -1;
        }else{
            selectedNode = store.find('id', selectedBill[0].getId());
        }
    },

    /**
     * Handle the compute button being clicked.
     */
    handleReset: function() {
        this.initalizeUploadForm(); 
    },

    /**
     * Handle the submit button being clicked.
     */
    handleSubmit: function() {
        var scope = this,
            store = this.getUtilityBillsStore();

        this.getUploadUtilityBillForm().getForm().submit({
            url: 'http://'+window.location.host+'/utilitybills/utilitybills',
            success: function() {
                store.reload();
            },
            failure: function(form, action) {
                utils.makeServerExceptionWindow(
                    'Unknown', 'Error', action.response.responseXML.body.innerHTML);
            }
        }); 
    },

    /**
     * Handle the compute button being clicked.
     */
    handleCompute: function() {
        var scope = this,
            selected = this.getUtilityBillsGrid().getSelectionModel().getSelection()[0];

        if (!selected)
            return;

        selected.set('action', 'compute');
    },

    /**
     * Handle the delete button being clicked.
     */
    handleDelete: function() {
        var scope = this,
            store = this.getUtilityBillsStore(),
            grid = this.getUtilityBillsGrid(),
            selected = this.getUtilityBillsGrid().getSelectionModel().getSelection()[0];

        if (!selected)
            return;

        Ext.Msg.confirm('Confirm deletion',
            'Are you sure you want to delete the selected utility bill?',
            function(answer) {
                if (answer == 'yes') {
                    store.remove(selected)
                    grid.fireEvent('deselect', selected, 0);
                }
            });
    },
    
    /**
     * Handle the toggle processed button being clicked.
     */
    handleToggleProcessed: function() {
        var grid = this.getUtilityBillsGrid(),
            selected = grid.getSelectionModel().getSelection()[0];

        if (!selected)
            return;
        selected.set('processed', !selected.get('processed'));
        var processed = selected.get('processed');
        this.getUtilbillCompute().setDisabled(processed);
    },

    handleUtilityComboChanged: function(utility_combo, record){
        var rate_class_store = Ext.getStore("RateClasses");
        rate_class_store.clearFilter(true);
        rate_class_store.filter('utility_id', record[0].data.id);
        var selected = this.getUtilityBillsGrid().getSelectionModel().getSelection()[0];
        var utility_store = this.getUtilityBillsStore();
        selected.set('rate_class', rate_class_store.getAt(0).data.name);
    },



    handleRateClassExpand: function(combo, record, index){
        utility_grid = combo.findParentByType('grid');
        selected = utility_grid.getSelectionModel().getSelection()[0];
        rate_class_store = Ext.getStore('RateClasses');
        rate_class_store.clearFilter(true);
        rate_class_store.filter('utility_id', selected.get('utility').id);
    },

    handleUtilityComboFocus: function(combo) {
        utility_grid = combo.findParentByType('grid');
        selected = utility_grid.getSelectionModel().getSelection()[0];
        combo.setValue(selected.get('utility').name);
    },

    updateCurrentAccountId: function() {
        this.getAccountLabel().setText(this.currentAccountId);
        // TODO: minimum/maximum account number
        if (this.currentAccountId == 1) {
            // TODO prev button
        } else if (this.currentAccountId == 10) {
            // TODO next button
        };
        var store = this.getUtilityBillsStore();
        store.getProxy().setExtraParam('id', this.currentAccountId)
    }
});
