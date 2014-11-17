Ext.define('Ext.slider.DynamicMultiSlider', {

    extend: 'Ext.slider.Multi',
    alias: 'widget.dynamicmultislider',

    removeThumbs: function(){
        var me = this;
        me.thumbs = [];
        me.innerEl.dom.innerHTML='';
    },

});
