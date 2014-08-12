Ext.define('Ext.ux.panel.PDF',{
    extend: 'Ext.panel.Panel',

    alias: 'widget.pdfpanel',

    floatable: false,
    titleCollapse: true,

    extraBaseCls: Ext.baseCSSPrefix + 'pdf',
    extraBodyCls: Ext.baseCSSPrefix + 'pdf-body',

    autoScroll: true,

    /**
     * @cfg{String} src
     * URL to the PDF - Same Domain or Server with CORS Support
     */
    src: '',

    /**
     * @cfg{Boolean} disableWorker
     * Disable workers to avoid yet another cross-origin issue(workers need the URL of
     * the script to be loaded, and currently do not allow cross-origin scripts)
     */
    disableWorker: true,

    /**
     * @cfg{Boolean} disableTextLayer
     * Enable to render selectable but hidden text layer on top of an PDF-Page.
     * This feature is buggy by now and needs more investigation!
     */
    disableTextLayer: false,
    
    /**
     * @cfg{String} loadingMessage
     * The text displayed when loading the PDF.
     */
    loadingMessage: 'Loading PDF, please wait...',

    pdfNotFoundMessage: 'PDF Not Found!',

    noSrcMessage: 'No PDF loaded',

    textRenderDelay: 20,

    initComponent: function(){
        var me = this,
            userItems = me.items || [],
            userDockedItems = me.dockedItems || [];

        me.bodyCls = me.bodyCls || '';
        me.bodyCls += (' ' + me.extraBodyCls);

        me.cls = me.cls || '';
        me.cls += (' ' + me.extraBaseCls);

        PDFJS.disableTextLayer = me.disableTextLayer;


        var textLayerDiv = '';
        if(!PDFJS.disableTextLayer){
            textLayerDiv = '<div class="pdf-text-layer"></div>';
        }

        userItems.push({
            itemId: 'pdfPageContainer',
            xtype: 'container',
            width: '100%',
            height: '100%',
            html: '<div class="pdf-canvas-layer"></div>' + textLayerDiv,
            listeners:{
                afterrender: function(){
                    me.canvasLayer = this.el.query('.pdf-canvas-layer')[0];
                    
                    if(!PDFJS.disableTextLayer){
                        me.textLayerDiv = this.el.query('.pdf-text-layer')[0];
                    }
                }
            }
        });
        me.items = userItems;

        me.callParent(arguments);

        me.on('afterrender', function(){
            if (!this.src)
                return; 
            
            me.loader = new Ext.LoadMask(me.child('#pdfPageContainer'),{
                msg: me.loadingMessage
            });
            me.loader.show();
        }, me,{
            single: true
        });

        if(me.disableWorker){
            PDFJS.disableWorker = true;
        }

    },

    onLoad: function(){
        var me = this;

        if(!!me.src){
            me.getDocument();
        }
    },

    onResize: function(){
        var me = this;
        me.renderDoc();
    },

    setSrc: function(src, regenBustCache){
        this.src = src;
        return this.getDocument(regenBustCache);
    },
    
    getDocument: function(regenBustCache){
        console.log('getDocument' + regenBustCache);
        var me = this;

        if(me._bustCache === undefined || regenBustCache === true){
            me._makeBustCache();
        }

        // Function to asyncronoulsy parse pages from the PDF
        var getPage = function(p) {
            me._pdfDoc.getPage(p).then(function (page) {
                me._pages[page.pageNumber-1] = page;
                page.getTextContent().then(function (textContent) {
                    console.log(textContent)
                    me._content[page.pageNumber-1] = textContent;
                    if (page.pageNumber < me._pdfDoc.numPages) {
                        getPage(page.pageNumber+1);
                    }else{
                        // Clear the PDF to free up memory
                        //console.log(me._content)
                        //me.renderDoc();
                    }
                });
            });
        };


        if(!!me.src){
            PDFJS.getDocument(me.src + '?_bc=' + me._bustCache).then(
            //success
            function(pdfDoc){
                me._pdfDoc = pdfDoc;
                me._pages = []
                me._content = []
                getPage(1);
            },
            //failure
            function(message, exception) {
                    console.log(message, exception);
            });
        }
        return me;
    },

    renderDoc: function(){
        console.log('renderDoc', this);
        var me = this;
        var panelWidth =  me.getWidth() - 20;

        if(!me._pdfDoc) {
            return;
        }

        if(panelWidth > 0) {
            while (me.textLayerDiv.lastChild) {
                me.textLayerDiv.removeChild(me.pageContainer.lastChild);
            }
            while (me.canvasLayer.lastChild) {
                me.canvasLayer.removeChild(me.canvasLayer.lastChild);
            }

            for(var i = 0; i < me._pages.length; i++) {
                var page = me._pages[i];
                var content  = me._content[i];
                me._makeAsyncRenderPageFunc(page, content)();
            }
        }
    },

    _renderPage: function(page, content){
        console.log('_renderPage ', page, content);
        var me = this;
        var panelWidth =  me.getWidth() - 20;
        var scale = (panelWidth) / page.getViewport(1.0).width;
        var viewport = page.getViewport(scale);
        var canvas = document.createElement('canvas');

        canvas.height = viewport.height;
        canvas.width = viewport.width;
        canvas.style.top = (page.pageNumber - 1) * viewport.height;
        me.canvasLayer.appendChild(canvas);
        var context = canvas.getContext('2d');

        page.render({
            canvasContext: context,
            viewport: viewport
        }).then(function(){
            me._makeAsyncRenderTextFunc(page, viewport, content)();
        });
    },

    _renderText: function(page, viewport, content){
        console.log('_renderText', page, viewport, content, typeof(content));
        var me = this;
        var textLayerSubDiv = document.createElement('div');
        textLayerSubDiv.style.height = viewport.height;
        textLayerSubDiv.style.width = viewport.width;
        textLayerSubDiv.style.top = (page.pageNumber - 1) * viewport.height;
        textLayerSubDiv.className = 'textLayer';

        var textLayer = new TextLayerBuilder({textLayerDiv: textLayerSubDiv,
                pageIndex: page.pageNumber, viewport: viewport,
                isViewerInPresentationMode: false});
        textLayer.setTextContent(content);
        me.textLayerDiv.appendChild(textLayerSubDiv);
    },

    _makeAsyncRenderPageFunc: function(page, content){
        console.log('_makeAsyncRenderPageFunc', page, content);
        var me = this;
        return function(){
            setTimeout(function() {me._renderPage(page, content);}, 0);
        };
    },

    _makeAsyncRenderTextFunc: function(page, viewport, content){
        var me = this;
        return function(){
            setTimeout(function() {me._renderText(page, viewport, content);},
                    page.pageNumber * me.textRenderDelay);
        };
    },

    _makeBustCache: function(){
        this._bustCache = Math.random()*100000000000000000;
    }

});