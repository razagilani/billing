'use strict';

angular.module('createExtractor.mainView', ['ngRoute'])

.config(['$routeProvider', function($routeProvider) {
  $routeProvider.when('/', {
    templateUrl: 'main-view/view.html',
    controller: 'mainViewCtrl'
  });
}])

.controller('mainViewCtrl', ['$scope', function($scope) {
	setUpPDFFunctions($scope);
	$scope.initPDFPanel();
	$scope.getDocument();
}]);

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
		$scope.src = "/create-extractor/test/utility_bill.pdf";
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
            console.log(renderScale, viewport, canvas)
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
                console.log(viewport, textLayerSubDiv)
                textLayer.setTextContent(content);
                $scope.textLayerDiv.append(textLayerSubDiv);
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

        $scope.resetLayers();
        Promise.all(execForAllPages(renderPage)).then(
            execForAllPages(renderPageText)
        );
	};

	/**
	* Loads the PDF document.
	*/
	$scope.getDocument = function(){
		if($scope.src === ''){
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
				console.log(message, exception);
				if(message.lastIndexOf('Missing PDF', 0) === 0){
					$scope.canvasLayer.innerHTML = $scope.pdfNotFoundMessage;
				}
			}
		);
	};
}
