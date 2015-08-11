angular.module('createExtractor').

directive("pdfPanel", ['DBService', 'dataModel', function(DBService, dataModel){
	return {
	    restrict: "ACE",
	    link: function(scope, element, attrs){
			/**  
			* Sets up PDF viewer. 
			* ( adapted from billing/billentry/static/ext/src/panel/PDF.js )
			* 
			* The PDF viewer is made up of two layers:
			* A canvas layer, containing a <canvas> tag for each page, that displays the PDF,
			* and a text layer, which contains selectable text overlayed on the PDF.  
			*/
			var initPDFPanel = function(){
				var pdf_data = {};
				dataModel.setPDFData(pdf_data);

			    /**
			     * @cfg{Boolean} disableWorker
			     * Disable workers to avoid yet another cross-origin issue(workers need the URL of
			     * the script to be loaded, and currently do not allow cross-origin scripts)
			     */
			    pdf_data.disableWorker = false;

			    /**
			     * @cfg{Boolean} disableTextLayer
			     * Enable to render selectable but hidden text layer on top of an PDF-Page.
			     * This feature is buggy by now and needs more investigation!
			     */
			    pdf_data.disableTextLayer = false;
			    
			    // messages to display while pdf is loading / if pdf rendering failed
			    pdf_data.loadingMessage =  '<div style="position: absolute; top: 200px; width: 100%; text-align: center">Loading PDF, please wait...</div>';
			    pdf_data.billNotFoundMessage = '<div style="position: absolute; top: 200px; width: 100%; text-align: center">Failed to load bill.</div>';
			    pdf_data.pdfNotLoadedMessage = '<div style="position: absolute; top: 200px; width: 100%; text-align: center">Failed to load PDF.</div>';
			    pdf_data.noSrcMessage = '<div style="position: absolute; top: 200px; width: 100%; text-align: center">No PDF selected</div>';

			    //current pdf src is a test file, eventually will be URL from server.
				//scope.src = "/create-extractor/test/utility_bill.pdf";
				pdf_data.cache = true;
				pdf_data.scale = 1.0;

				PDFJS.disableTextLayer = pdf_data.disableTextLayer;

				//set up canvas layer for PDF
			    var canvasLayerHTML = '<div class="pdf-canvas-layer"></div>';
			    element.find('.pdf-scroll').append(canvasLayerHTML);
			    pdf_data.canvasLayer = angular.element('div[pdf-panel] .pdf-scroll .pdf-canvas-layer');

			    //if enabled, set up text for PDF
			    var textLayerHTML = '';
			    if(!PDFJS.disableTextLayer){
			        textLayerHTML = '<div class="pdf-text-layer"></div>';
				    element.find('.pdf-scroll').append(textLayerHTML);
			    	pdf_data.textLayerDiv = angular.element('div[pdf-panel] .pdf-scroll .pdf-text-layer');
			    }

				// canvas for drawing bounding boxes
				pdf_data.bboxCanvas = angular.element("canvas[bbox-drawing]");
			};

			/**
			* Removes child elements (which correspond to pages of the PDF) from 
			* the canvas and text layers.
			*/
			var resetLayers = function(){
				var pdf_data = dataModel.pdf_data();
				pdf_data.canvasLayer.empty();
				pdf_data.textLayerDiv.empty();
			};

			/**
			* Displays a 'loading...' message, and resets the pdf 
			* viewer's canvas and text layers.
			*/
			var setLoading = function(){
				var pdf_data = dataModel.pdf_data();
				resetLayers();
				pdf_data.canvasLayer.html(pdf_data.loadingMessage);
				pdf_data.pages = [];
			};

			var renderDoc = function(){
				var pdf_data = dataModel.pdf_data();
				var pdfDoc = pdf_data.pdfDoc;
				var panelWidth = angular.element('div[pdf-panel]').width();
				var renderScale;

		        if(!pdfDoc || panelWidth <= 0)
		            return Promise.resolve(null);

		        var makePageLayer = function(tag, pageNumber, width, height, classes){
			        var cls = classes || '';
			        var elem = document.createElement(tag);
			        elem.height = height;
			        elem.width = width;
			        elem.style.top = (pageNumber - 1) * height + 'px';
			        elem.className = cls;
			        return elem;
		    	};

		    	/**
		    	* Render a page from a PDF, and add a canvas tag that displays it.
		    	*/
		    	var renderPage = function(page){
		            // The scale can only be set once the first page of the document has
		            // been retrieved
		            if(!renderScale)
		                renderScale = panelWidth / page.getViewport(pdf_data.scale).width;
		            var viewport = page.getViewport(renderScale);
		            var canvas = makePageLayer(
		                'canvas', page.pageNumber, viewport.width, viewport.height
		            );
		            pdf_data.canvasLayer.append(canvas);

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

		                var textLayer = new TextLayerBuilder({
		                    textLayerDiv: textLayerSubDiv,
		                    pageIndex: page.pageNumber,
		                    viewport: viewport,
		                    isViewerInPresentationMode: false
		                });
		                textLayer.setTextContent(content);
		                pdf_data.textLayerDiv.append(textLayerSubDiv);
		            });
		        };

		        /* 
		        * Store coordinates of a page. 
		        * This can be retrieved later without using pdf.js' PDFDocument.getPage(), 
		        * which is asynchronous.
		        */
		        var storePageCoords = function(page){
		        	if (pdf_data.pages == undefined){
		        		pdf_data.pages = [];
		        	}
		        	var viewport = page.getViewport(1); 
		        	pdf_data.pages.push({
		        		pageNumber: page.pageNumber,
		        		width: viewport.width,
		        		height: viewport.height
		        	});
		        };

		        /**
		        *  Set up bbox drawing canvas size to match PDF canvas's size
				*  (this can't be done in css, since the canvas becomes 'zoomed in')
				*/
		        var initBboxDrawingCanvas = function(){
					pdf_data.bboxCanvas.attr("width", pdf_data.canvasLayer.width());
					pdf_data.bboxCanvas.attr("height", pdf_data.canvasLayer.height());
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

		        resetLayers();
		        return Promise.all(execForAllPages(renderPage)).
		        	then(execForAllPages(renderPageText)).
		        		then(execForAllPages(storePageCoords)).
		        			then(initBboxDrawingCanvas);
			};

			/**
			* Loads the PDF document.
			*/
			var getDocument = function(){
				var pdf_data = dataModel.pdf_data();
				if(pdf_data.src === '' || pdf_data.src === undefined){
					pdf_data.canvasLayer.html(pdf_data.noSrcMessage);
					return;
				}
				else {
					setLoading();
				}

				/**
				* Adds a random number to the end of the reqested URL, so browser won't just get the cached PDF.
				*/
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
				return PDFJS.getDocument(pdf_data.src).then(
					// on success
					function(pdfDoc){
						pdf_data.pdfDoc = pdfDoc;
						renderDoc();
					},
					// on fail
					function(message, exception){
						pdf_data.canvasLayer.html(pdf_data.pdfNotLoadedMessage);
						throw "Load PDF Error";
					}
				);
			};

			initPDFPanel();
			//refresh pdf when bill_id is changed
			scope.$watch('bill_id', function(newValue, oldValue){
				if(!scope.bill_id){
					return;
				}

				var loadBill = function(){
					return DBService.getUtilBill(scope.bill_id).then(null, loadBillError);
				}

				var loadPDF = function(response){
					var bill = response.data;
					scope.pdf_data().src = bill.pdf_url;
					return getDocument();
				};

				var loadLayoutElements = function(){
					return DBService.getLayoutElements(scope.bill_id).then(
						// on success
						function(response){
							scope.pdf_data().layout_elements = response.data.layout_elements;
						},
						// on error
						function(){
							console.log("Failed to get layout elements");
							scope.pdf_data().layout_elements = null;
						}
					)
				};

				var getFieldOffsets = function(){
					scope.selected = null;

					// update offset objects for drawing individual fields
					var offsetTasks = [];
					scope.extractor().fields.forEach(function(field){
						offsetTasks.push(scope.updateOffset(field));
					});
					return Promise.all(offsetTasks).then(scope.paintCanvas);
				}

				var loadBillError = function(){
					scope.pdf_data().canvasLayer.html(scope.pdf_data().billNotFoundMessage);
					throw "Load Bill Error";
				};

				// clear these so as not to cause confusion while new bill loads.
				scope.pdf_data().layout_elements = null;
				scope.clearCanvas();
				loadBill()
				.then(loadPDF)
				.then(loadLayoutElements)
				.then(getFieldOffsets)
				.finally(scope.paintCanvas);
			});

			scope.$watch('pdf_data().scale', function(){
				// renderDoc is (relatively) slow, and clearCanvas prevents old bounding boxes from hanging around while the PDF is zooming in.
				scope.clearCanvas();
				renderDoc().then(scope.paintCanvas);
			});
		}	
	};
}]);