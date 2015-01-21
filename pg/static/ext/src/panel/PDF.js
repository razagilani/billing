Ext.define('Ext.panel.PDF',{
    extend: 'Ext.panel.Panel',

    alias: 'widget.pdfpanel',

    floatable: false,
    titleCollapse: true,
    header: false,

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
    disableWorker: false,

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
    loadingMessage: '<div style="position: absolute; top: 200px; width: 100%; text-align: center">Loading PDF, please wait...</div>',

    pdfNotFoundMessage: '<div style="position: absolute; top: 200px; width: 100%; text-align: center">PDF NOT FOUND</div>',

    noSrcMessage: '<div style="position: absolute; top: 200px; width: 100%; text-align: center">No PDF selected</div>',

    textRenderDelay: 20,

    cache: true,

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

        if(me.disableWorker){
            PDFJS.disableWorker = true;
        }else{
            PDFJS.workerSrc = 'static/ext/lib/pdf.js/pdf.worker.js'
        }
    },

    onLoad: function(){
        var me = this;
        me.getDocument();
    },

    onResize: function(){
        var me = this;
        if(me.src !== '') {
            me.renderDoc(me);
        }else{
            me.getDocument();
        }
    },

    setSrc: function(src, regenBustCache){
        this.src = src;
        return this.getDocument(regenBustCache);
    },

    setLoading: function(){
        this.canvasLayer.innerHTML = this.loadingMessage;
    },
    
    getDocument: function(regenBustCache){
        var me = this;

        if(me._bustCache === undefined || regenBustCache === true){
            me._makeBustCache();
        }

        if(me.src === ''){
            me.canvasLayer.innerHTML = me.noSrcMessage;
            return
        }else{
            me.setLoading();
        }

        // Function to asyncronoulsy parse pages from the PDF
        var getPage = function(p) {
            me._pdfDoc.getPage(p).then(function (page) {
                me._pages[page.pageNumber-1] = page;
                page.getTextContent().then(function (textContent) {
                    me._content[page.pageNumber-1] = textContent;
                    if (page.pageNumber < me._pdfDoc.numPages) {
                        getPage(page.pageNumber+1);
                    }else{
                        // Clear the PDF to free up memory
                        me._pdfDoc = {};
                        me.renderDoc(me);
                    }
                });
            });
        };

        var cacheparam;
        if(!me.cache){
            cacheparam = '?_bc=' + me._bustCache;
        }else{
            cacheparam = '';
        }

        PDFJS.getDocument(me.src + cacheparam).then(
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
            if(message.lastIndexOf('Missing PDF', 0) === 0){
                me.canvasLayer.innerHTML = me.pdfNotFoundMessage;
            }
        });
        return me;
    },

    renderDoc: function(scope){
        var me = scope;
        var panelWidth =  me.width - 20;

        if(!me._pdfDoc) {
            return;
        }

        if(panelWidth > 0) {
            while (me.textLayerDiv.lastChild) {
                me.textLayerDiv.removeChild(me.textLayerDiv.lastChild);
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
        var me = this;
        var panelWidth =  me.width - 20;
        var scale = (panelWidth) / page.getViewport(1.0).width;
        var viewport = page.getViewport(scale);
        var canvas = document.createElement('canvas');

        canvas.height = viewport.height;
        canvas.width = viewport.width;
        canvas.style.top = (page.pageNumber - 1) * viewport.height  + 'px';
        me.canvasLayer.appendChild(canvas);
        var context = canvas.getContext('2d');

        page.render({
            canvasContext: context,
            viewport: viewport
        }).then(function(){
            me._makeAsyncRenderTextFunc(page, content)();
        });
    },

    _renderText: function(page, content){
        var me = this;
        var panelWidth =  me.width - 20;
        var scale = (panelWidth) / page.getViewport(1.0).width;
        var viewport = page.getViewport(scale);
        var textLayerSubDiv = document.createElement('div');

        textLayerSubDiv.className = 'textLayer';
        textLayerSubDiv.style.height = viewport.height + 'px';
        textLayerSubDiv.style.width = viewport.width + 'px';
        textLayerSubDiv.style.top = ((page.pageNumber - 1) * viewport.height)  + 'px';

        var textLayer = new TextLayerBuilder({textLayerDiv: textLayerSubDiv,
                pageIndex: page.pageNumber, viewport: viewport,
                isViewerInPresentationMode: false});
        textLayer.setTextContent(content);
        me.textLayerDiv.appendChild(textLayerSubDiv);
    },

    _makeAsyncRenderPageFunc: function(page, content){
        var me = this;
        return function(){
            setTimeout(function() {me._renderPage(page, content);}, 0);
        };
    },

    _makeAsyncRenderTextFunc: function(page, content){
        var me = this;
        return function(){
            setTimeout(function() {me._renderText(page, content);},
                    page.pageNumber * me.textRenderDelay);
        };
    },

    _makeBustCache: function(){
        this._bustCache = Math.random()*100000000000000000;
    }

});
