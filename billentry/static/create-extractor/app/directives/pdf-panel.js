angular.module('createExtractor').

directive("pdfPanel", ['DBService', function(DBService){
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
				var pdf_data = {} 
				scope.pdf_data = pdf_data;

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
			    pdf_data.pdfNotFoundMessage = '<div style="position: absolute; top: 200px; width: 100%; text-align: center">PDF NOT FOUND</div>';
			    pdf_data.noSrcMessage = '<div style="position: absolute; top: 200px; width: 100%; text-align: center">No PDF selected</div>';

			    //current pdf src is a test file, eventually will be URL from server.
				//scope.src = "/create-extractor/test/utility_bill.pdf";
				pdf_data.cache = true;
				pdf_data.scale = 1.0;

				PDFJS.disableTextLayer = pdf_data.disableTextLayer;

				//set up canvas layer for PDF
			    var canvasLayerHTML = '<div class="pdf-canvas-layer"></div>';
			    angular.element('div[pdf-panel]').append(canvasLayerHTML);
			    pdf_data.canvasLayer = angular.element('div[pdf-panel] .pdf-canvas-layer');

			    //if enabled, set up text for PDF
			    var textLayerHTML = '';
			    if(!PDFJS.disableTextLayer){
			        textLayerHTML = '<div class="pdf-text-layer"></div>';
				    angular.element('div[pdf-panel]').append(textLayerHTML);
			    	pdf_data.textLayerDiv = angular.element('div[pdf-panel] .pdf-text-layer');
			    }

				// canvas for drawing bounding boxes
				pdf_data.bboxCanvas = angular.element("canvas[bbox-drawing]");
			};

			/**
			* Removes child elements (which correspond to pages of the PDF) from 
			* the canvas and text layers.
			*/
			var resetLayers = function(){
				var pdf_data = scope.pdf_data;
				 pdf_data.canvasLayer.empty();
				 pdf_data.textLayerDiv.empty();
			};

			/**
			* Displays a 'loading...' message, and resets the pdf 
			* viewer's canvas and text layers.
			*/
			var setLoading = function(){
				var pdf_data = scope.pdf_data;
				resetLayers();
				pdf_data.canvasLayer.html(pdf_data.loadingMessage);
			};

			var renderDoc = function(){
				var pdf_data = scope.pdf_data;
				var pdfDoc = pdf_data.pdfDoc;
				var panelWidth = angular.element('div[pdf-panel]').width();
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
		        Promise.all(execForAllPages(renderPage)).
		        	then(execForAllPages(renderPageText)).
		        		then(execForAllPages(storePageCoords)).
		        			then(initBboxDrawingCanvas);
			};

			/**
			* Loads the PDF document.
			*/
			var getDocument = function(){
				var pdf_data = scope.pdf_data;

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
				PDFJS.getDocument(pdf_data.src).then(
					// on success
					function(pdfDoc){
						pdf_data.pdfDoc = pdfDoc;
						renderDoc();
					},
					// on fail
					function(message, exception){
						console.log(message);
						console.log(exception);
						if(message.message.lastIndexOf('Missing PDF', 0) === 0){
							pdf_data.canvasLayer.html(pdf_data.pdfNotFoundMessage);
						}
					}
				);
			};

			initPDFPanel();
			getDocument();
			scope.$watch('bill_id', function(newValue, oldValue){
				DBService.getUtilBill(scope.bill_id)
					.success(function(bill){
						scope.pdf_data.src = bill.pdf_url;
						getDocument();
				});
			});
		}
	};
}]).

//directive for a canvas in which one can draw bounding boxes
directive("bboxDrawing", function(){
	return {
	    restrict: "A",
	    link: function(scope, element){
			var startX;
			var startY;
			var currentX;
			var currentY;

			var drawing = false;

			/**
			* If drawing is activated, start drawing a rectangle on mouse down
			*/
			element.bind('mousedown', function(event){
				if (scope.bboxActive){
				    if(event.offsetX!==undefined){
				    	startX = event.offsetX;
				    	startY = event.offsetY;
				    } else { // Firefox compatibility
				    	startX = event.layerX - event.currentTarget.offsetLeft;
				    	startY = event.layerY - event.currentTarget.offsetTop;
				    }
				    drawing = true;
				}
			});

			/**
			* While drawing, update the rectangle when the mouse moves
			*/
	    	element.bind('mousemove', function(event){
	    		if(scope.bboxActive && drawing){
					// get current mouse position
					if(event.offsetX!==undefined){
						currentX = event.offsetX;
						currentY = event.offsetY;
					} else {
						currentX = event.layerX - event.currentTarget.offsetLeft;
						currentY = event.layerY - event.currentTarget.offsetTop;
					}

					var minX = Math.min(startX, currentX);
					var minY = Math.min(startY, currentY);
					var maxX = Math.max(startX, currentX);
					var maxY = Math.max(startY, currentY);

					coords = canvasToPDFCoords(minX, minY, maxX	, maxY);

					if (scope.selected.bounding_box == null){
						scope.selected.bounding_box = {};
					}
					scope.selected.bounding_box.x0 = coords.x0;
					scope.selected.bounding_box.y0 = coords.y0;
					scope.selected.bounding_box.x1 = coords.x1;
					scope.selected.bounding_box.y1 = coords.y1;

					drawBoundingBoxes();
		        }

	    	});

			/**
			* When the user lets go the mouse, deactivate drawing to prevent accidental editing.
			*/
			element.bind('mouseup', function(event){
				// stop drawing, deactive bounding box
				drawing = false;
				scope.bboxActive = false;
				scope.$apply();
			});

			/**
			* Draws bounding boxes on the canvas. Bounding boxes are colored differently 
			* if they are currently selected, enabled or disabled, etc. 
			*/
			function drawBoundingBoxes(){
				// clear previous rectangles
				var ctx = element[0].getContext('2d');
				ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
				if (scope.extractor().fields == undefined){
					return;
				};
				scope.extractor().fields.forEach(function(field){
			  		if (field.bounding_box == null || field.bounding_box.x0 == null){
			  			return;
			  		}

			  		var opacity = 1;
			  		var color;
			  		if (scope.selected && field.applier_key == scope.selected.applier_key){
			  			color = "#FF0000";
			  		}
			  		else if (field.enabled == false){
			  			color = "#AAAAFF";
			  		}
			  		else {
						color = "#000066";
			  		}

			  		var pageCanvases = scope.pdf_data.canvasLayer.children();
			  		for(var i=0; i<pageCanvases.length; i++){
			  			if (field.page_number != null && (i+1 < field.page_number || (i+1 > field.page_number && field.max_page != null && i+1 > field.max_page))){
			  				opacity = 0.5;
			  			}
			  			var coords = PDFToCanvasCoords(field.bounding_box, i+1);
			  			console.log(i+1);
			  			console.log(coords);
			  			console.log("---");
				  		drawBBOX(coords, color, opacity);
			  		}
				});
		  	}

			// draw an individual bounding box, in canvas coordinates
	    	function drawBBOX(coords, color, opacity){
				var ctx = element[0].getContext('2d');
				// start drawing
				ctx.beginPath();
				// set stroke opacity, color and thickness
				ctx.globalAlpha = opacity;
				ctx.strokeStyle = color;
				ctx.lineWidth = 2;
				// specify rectangle
				ctx.rect(coords.x0, coords.y0, coords.x1 - coords.x0, coords.y1 - coords.y0);
				// draw the rectangle
				ctx.stroke();
				// reset alpha
				ctx.globalAlpha = 1;
				// stop drawing
				ctx.closePath()
	    	}

		  	/**
		  	* Converts pixel coordinate of the canvas to the coordinates on the PDF. 
		  	* scaled the coordinates to the actual size of the pdf, and then inverts y values
		  	* (so y=0 is at the bottom of the page).
		  	*/
		  	function canvasToPDFCoords(x0, y0, x1, y1){
		  		//find correct page
		  		var pageMaxY = y1; 
		  		var pageCanvases = scope.pdf_data.canvasLayer.children();
		  		var i = 0;
		  		var pageCanvas;
		  		for(i=0; i<pageCanvases.length; i++){
					pageCanvas = pageCanvases[i];
					if (pageMaxY < pageCanvas.height){
						break;
					}
					pageMaxY -= pageCanvas.height;
				}
				var pageMinY = pageMaxY - (y1 - y0);

				// scale coordinates based on page size
				var actualPageHeight = scope.pdf_data.pages[i].height;
				var sc = actualPageHeight / pageCanvas.height;
				var scaledCoords = scale({x0: x0, y0: pageMinY, x1: x1, y1: pageMaxY }, sc);

				//invert y values
				var old_y0 = scaledCoords.y0;
				scaledCoords.y0 = actualPageHeight - scaledCoords.y1;
				scaledCoords.y1 = actualPageHeight - old_y0;

				return scaledCoords;
		  	}

		  	/*
		  	* Converts pdf coordinates (with inverted y, so y=0 is at the bottom of the page)
		  	*/
		  	function PDFToCanvasCoords(obj, page_num){
		  		var canvas_height = scope.pdf_data.canvasLayer.children()[page_num - 1].height;
		  		var page_height = scope.pdf_data.pages[page_num - 1].height;

		  		// invert y
		  		var minY = page_height - obj.y1;
		  		var maxY = page_height - obj.y0;

		  		// scale
		  		var sc = canvas_height / page_height;
		  		var coords = scale({x0: obj.x0, y0: minY, x1: obj.x1, y1: maxY}, sc);

		  		// increase y values to line up to curent page
		  		for(var i=0; i<page_num-1; i++){
		  			var current_page_height = scope.pdf_data.canvasLayer.children()[i].height;
		  			coords.y0 += current_page_height;
		  			coords.y1 += current_page_height;
		  		}

		  		return coords;

		  	}

		  	// scales the coordinates in 'coords' by a factor of 'sc'
		  	function scale(coords, sc){
		  		return { x0: coords.x0*sc, y0: coords.y0*sc, x1: coords.x1*sc, y1: coords.y1*sc };
		  	}

			// canvas reset
			function reset(){
				element[0].width = element[0].width; 
			}

			// watch selected field, so one can highlight only the selected bounding box 
			scope.$watch('selected', function(newValue, oldValue){
				drawBoundingBoxes();
			});
	    }
	};
});