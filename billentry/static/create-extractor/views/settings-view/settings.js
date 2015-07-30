'use strict';

angular.module('createExtractor.settingsView', ['ngRoute', 'DBService', 'model']).

controller('settingsViewCtrl', ['$scope', 'DBService', 'dataModel', function($scope, DBService, dataModel) {
	// initialize data model
	dataModel.initDataModel();
	$scope.extractor = dataModel.extractor();
	$scope.applier_keys = dataModel.applier_keys();
	$scope.field_types = dataModel.field_types();
	$scope.data_types = dataModel.data_types();

	// canvas for drawing bounding boxes
	$scope.bboxCanvas = angular.element("#bbox-drawing-canvas");

	//set up pdf viewer
	setUpPDFFunctions($scope);
	DBService.getUtilBill(24153)
		.success(function(bill){
			$scope.src = bill.pdf_url;
			$scope.initPDFPanel();
			$scope.getDocument();
	});

	// initialize values for bounding box corners 
	$scope.corners = [
		{name: "Top Left", value: 0},
		{name: "Top Right", value: 1},
		{name: "Bottom Left", value: 2},
		{name: "Bottom Right", value: 3}];

	/**
	* Create an array of page numbers for the current PDF document. 
	 * 'withNull' specifies whether to provide a 'null' option for the page number.
	*/
	$scope.getPDFPageNums = function(withNull){
		var pdfPageNums = withNull ? [null] : [];
		if($scope.pdfDoc){
			for(var i = 1; i <= $scope.pdfDoc.numPages; i++){
				pdfPageNums.push(i);	
			}
		}
		return pdfPageNums;
	}

	$scope.selected = null;
	// select a field, so one can view/edit its parameters
	$scope.selectField = function(field){
		if (!field.enabled){
			$scope.enableField(field);
			$scope.selected = field;
		} 
		// clicking on an already selected field de-selects it unless it was disabled.
		else {
			if ($scope.selected == field){
				$scope.selected = null;
			} else {
				$scope.selected = field;
			}
		}
	}
	// enable a field, so that it will be used in extraction
	$scope.enableField = function(field){
		field.enabled = !field.enabled;
		$scope.drawBoundingBoxes();
	}

	// allow the bounding box to be edited. 
	// This is in place so that people don't undo bounding boxes by accidentally clicking, etc.
	$scope.activateBoundingBox = function(){
		if ($scope.bboxActive == undefined){
			$scope.bboxActive = false;
		}
		$scope.bboxActive = !$scope.bboxActive;
	}

	/**
	* Draws bounding boxes on the canvas. Bounding boxes are colored differently 
	* if they are currently selected, enabled or disabled, etc. 
	*/
	$scope.drawBoundingBoxes = function(){
		// clear previous rectangles
		var ctx = $scope.bboxCanvas[0].getContext('2d');
		ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
		$scope.extractor.fields.forEach(function(elem){
	  		if (elem.bounding_box == null || elem.bounding_box.x0 == null){
	  			return;
	  		}

	  		var color;
	  		if ($scope.selected && elem.applier_key == $scope.selected.applier_key){
	  			color = "#FF0000";
	  		}
	  		else if (elem.enabled == false){
	  			color = "#AAAAFF";
	  		}
	  		else {
				color = "#000066";
	  		}
	  		drawBBOX(elem.bounding_box.x0, 
	  				 elem.bounding_box.y0, 
	  				 elem.bounding_box.x1, 
	  				 elem.bounding_box.y1, 
	  				 color);
		});

		// draw an individual bounding box
    	function drawBBOX(x0, y0, x1, y1, color){
			// start drawing
			ctx.beginPath();
			// set stroke color and thickness
			ctx.strokeStyle = color;
			ctx.lineWidth = 2;
			// specify rectangle
			ctx.rect(x0, y0, x1 - x0, y1 - y0);
			// draw the rectangle
			ctx.stroke();
			// stop drawing
			ctx.closePath()
    	}
  	}

	// Update the canvas when fields are selected or enabled/disabled
	$scope.$watch('selected', function(newValue, oldValue){
		$scope.drawBoundingBoxes();
	});
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

			var drawing = true;

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

					scope.selected.bounding_box.x0 = Math.min(startX, currentX);
					scope.selected.bounding_box.y0 = Math.min(startY, currentY);
					scope.selected.bounding_box.x1 = Math.max(startX, currentX);
					scope.selected.bounding_box.y1 = Math.max(startY, currentY);

					scope.drawBoundingBoxes();
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

			// canvas reset
			function reset(){
				element[0].width = element[0].width; 
			}
	    }
	};
});

/**
* Sets up functions for manipulating the PDF viewer, and adds those functions to $scope. 
*/
function setUpPDFFunctions($scope) {
	/**  
	* Sets up PDF viewer. 
	* ( adapted from billing/billentry/static/ext/src/panel/PDF.js )
	* 
	* The PDF viewer is made up of two layers:
	* A canvas layer, containing a <canvas> tag for each page, that displays the PDF,
	* and a text layer, which contains selectable text overlayed on the PDF.  
	*/
	$scope.initPDFPanel = function(){
		
	    /**
	     * @cfg{Boolean} disableWorker
	     * Disable workers to avoid yet another cross-origin issue(workers need the URL of
	     * the script to be loaded, and currently do not allow cross-origin scripts)
	     */
	    $scope.disableWorker = false;

	    /**
	     * @cfg{Boolean} disableTextLayer
	     * Enable to render selectable but hidden text layer on top of an PDF-Page.
	     * This feature is buggy by now and needs more investigation!
	     */
	    $scope.disableTextLayer = false;
	    
	    // messages to display while pdf is loading / if pdf rendering failed
	    $scope.loadingMessage =  '<div style="position: absolute; top: 200px; width: 100%; text-align: center">Loading PDF, please wait...</div>';
	    $scope.pdfNotFoundMessage = '<div style="position: absolute; top: 200px; width: 100%; text-align: center">PDF NOT FOUND</div>';
	    $scope.noSrcMessage = '<div style="position: absolute; top: 200px; width: 100%; text-align: center">No PDF selected</div>';

	    //current pdf src is a test file, eventually will be URL from server.
		//$scope.src = "/create-extractor/test/utility_bill.pdf";
		$scope.cache = true;
		$scope.scale = 1.0;

		PDFJS.disableTextLayer = $scope.disableTextLayer;

		//set up canvas layer for PDF
	    var canvasLayerHTML = '<div class="pdf-canvas-layer"></div>';
	    angular.element('#pdf-container').append(canvasLayerHTML);
	    $scope.canvasLayer = angular.element('#pdf-container .pdf-canvas-layer');

	    //if enabled, set up text for PDF
	    var textLayerHTML = '';
	    if(!PDFJS.disableTextLayer){
	        textLayerHTML = '<div class="pdf-text-layer"></div>';
		    angular.element('#pdf-container').append(textLayerHTML);
	    	$scope.textLayerDiv = angular.element('#pdf-container .pdf-text-layer');
	    }
	}

	/**
	* Removes child elements (which correspond to pages of the PDF) from 
	* the canvas and text layers.
	*/
	$scope.resetLayers = function(){
		while ($scope.textLayerDiv.lastChild) {
            $scope.textLayerDiv.removeChild($scope.textLayerDiv.lastChild);
        }
        while ($scope.canvasLayer.lastChild) {
            $scope.canvasLayer.removeChild($scope.canvasLayer.lastChild);
        }
	};

	/**
	* Displays a 'loading...' message, and resets the pdf 
	* viewer's canvas and text layers.
	*/
	$scope.setLoading = function(){
		$scope.resetLayers();
		$scope.canvasLayer.innerHTML = $scope.loadingMessage;
	};

	$scope.renderDoc = function(){
		var pdfDoc = $scope.pdfDoc;
		var panelWidth = angular.element('#pdf-container').width();
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
                renderScale = panelWidth / page.getViewport($scope.scale).width;
            var viewport = page.getViewport(renderScale);
            var canvas = makePageLayer(
                'canvas', page.pageNumber, viewport.width, viewport.height
            );
            $scope.canvasLayer.append(canvas);

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

                // textLayerSubDiv.addEventListener(
                //     'dblclick', function(e){$scope.handleLayerClick.call($scope,e)}, true
                // );

                var textLayer = new TextLayerBuilder({
                    textLayerDiv: textLayerSubDiv,
                    pageIndex: page.pageNumber,
                    viewport: viewport,
                    isViewerInPresentationMode: false
                });
                textLayer.setTextContent(content);
                $scope.textLayerDiv.append(textLayerSubDiv);
            });
        };


        /**
        *  Set up bbox drawing canvas size to match PDF canvas's size
		*  (this can't be done in css, since the canvas becomes 'zoomed in')
		*/
        var initBboxDrawingCanvas = function(){
			$scope.bboxCanvas.attr("width", $scope.canvasLayer.width());
			$scope.bboxCanvas.attr("height", $scope.canvasLayer.height());
        }

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

        $scope.resetLayers();
        Promise.all(execForAllPages(renderPage)).
        	then(execForAllPages(renderPageText)).
        		then(initBboxDrawingCanvas);
	};

	/**
	* Loads the PDF document.
	*/
	$scope.getDocument = function(){

		if($scope.src === '' || $scope.src === undefined){
			$scope.canvasLayer.innerHTML = $scope.noSrcMessage;
			return;
		}
		else {
			$scope.setLoading();
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

		PDFJS.getDocument($scope.src).then(
			// on success
			function(pdfDoc){
				$scope.pdfDoc = pdfDoc;
				$scope.renderDoc();
			},
			// on fail
			function(message, exception){
				console.log(message);
				console.log(exception);
				if(message.message.lastIndexOf('Missing PDF', 0) === 0){
					$scope.canvasLayer.innerHTML = $scope.pdfNotFoundMessage;
				}
			}
		);
	};
}
