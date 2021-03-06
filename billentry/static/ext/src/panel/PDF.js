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

    cache: true,

    scale: 1.0,

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

        userDockedItems.push({
            xtype: 'toolbar',
            dock: 'bottom',
            items: ['->',{
                xtype: 'button',
                text: '+ Zoom In',
                handler: function(){me.zoomIn.call(me)}
            },{
                xtype: 'button',
                text: '&#151; Zoom Out',
                handler: function(){me.zoomOut.call(me)}
            }]
        });
        me.dockedItems = userDockedItems;

        me.callParent(arguments);

        if(me.disableWorker){
            PDFJS.disableWorker = true;
        }else{
            PDFJS.workerSrc = 'ext/lib/pdf.js/pdf.worker.js'
        }
    },

    onLoad: function(){
        this.getDocument();
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
        this.resetLayers();
        this.canvasLayer.innerHTML = this.loadingMessage;
    },

    resetLayers: function(){
        while (this.textLayerDiv.lastChild) {
            this.textLayerDiv.removeChild(this.textLayerDiv.lastChild);
        }
        while (this.canvasLayer.lastChild) {
            this.canvasLayer.removeChild(this.canvasLayer.lastChild);
        }
    },
    
    getDocument: function(regenBustCache){
        var me = this;

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

        var makeFullUrl = function(){
            var cacheparam;
            if(!me.cache){
                if(me._bustCache === undefined || regenBustCache === true){
                    me._bustCache = Math.random()*100000000000000000;
                }
                cacheparam = '?_bc=' + me._bustCache;
            }else{
                cacheparam = '';
            }
            return me.src + cacheparam
        };

        PDFJS.getDocument(makeFullUrl()).then(function(pdfDoc){
            // Maintain a reference to the document so that it can be rerendered
            // when the size or scale of the panel changes
            me._pdfDoc = pdfDoc;
            me.renderDoc();
        }, function(message, exception){
            console.log(message, exception);
            if(message.lastIndexOf('Missing PDF', 0) === 0){
                me.canvasLayer.innerHTML = me.pdfNotFoundMessage;
            }
        });
        return me;
    },

    renderDoc: function(){
        var me = this;
        var pdfDoc = me._pdfDoc;
        var panelWidth =  me.width - 20;
        var renderScale;

        if(!pdfDoc || panelWidth <= 0)
            return;

        var makePageLayer = function(tag, pageNumber, width, height, classes){
            var cls = classes || '';
            var elem = document.createElement(tag);
            elem.height = height;
            elem.width = width;
            elem.style.top = (pageNumber - 1) * height + 'px';
            elem.className = cls;
            return elem;
        };

        var renderPage = function(page){
            // The scale can only be set once the first page of the document has
            // been retrieved
            if(!renderScale)
                renderScale = panelWidth / page.getViewport(me.scale).width;
            var viewport = page.getViewport(renderScale);
            var canvas = makePageLayer(
                'canvas', page.pageNumber, viewport.width, viewport.height
            );
            me.canvasLayer.appendChild(canvas);

            // This returns a Promise that fires when the page has rendered
            return page.render({
                canvasContext: canvas.getContext('2d'),
                viewport: viewport
            });
        };

        var renderPageText = function(page){
            return page.getTextContent().then(function(content){
                var viewport = page.getViewport(renderScale);
                var textLayerSubDiv = makePageLayer(
                    'div', page.pageNumber, viewport.width, viewport.height,
                    'textLayer'
                );
                textLayerSubDiv.addEventListener(
                    'dblclick', function(e){me.handleLayerClick.call(me,e)}, true
                );

                var textLayer = new TextLayerBuilder({
                    textLayerDiv: textLayerSubDiv,
                    pageIndex: page.pageNumber,
                    viewport: viewport,
                    isViewerInPresentationMode: false
                });
                textLayer.setTextContent(content);
                me.textLayerDiv.appendChild(textLayerSubDiv);
            });
        };

        var execForAllPages = function(func){
            // Retrieves all pages and executes a func on them
            // Returns an Array of func's return value
            var pageTasks = [];
            for(var i = 1; i <= pdfDoc.numPages; i++) {
                pageTasks.push(
                    pdfDoc.getPage(i).then(func)
                )
            }
            return pageTasks;
        };

        this.resetLayers();
        Promise.all(execForAllPages(renderPage)).then(
            execForAllPages(renderPageText)
        );
    },

    handleLayerClick: function(mouseEvent){
        mouseEvent.shiftKey ? this.zoomOut.call(this) : this.zoomIn.call(this);
    },

    zoomIn: function(){
        this.scale -= 0.2;
        this.renderDoc();
    },

    zoomOut: function(){
        if (this.scale <= 0.8) {
            this.scale += 0.2;
            this.renderDoc();
        }
    }

});
