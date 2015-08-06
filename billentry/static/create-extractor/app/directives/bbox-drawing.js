angular.module('createExtractor').

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
				if (scope.bboxActive || scope.marginActive){
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
	    		if (drawing){
					// get current mouse position
					if(event.offsetX!==undefined){
						currentX = event.offsetX;
						currentY = event.offsetY;
					} else {
						currentX = event.layerX - event.currentTarget.offsetLeft;
						currentY = event.layerY - event.currentTarget.offsetTop;
					}

		    		if(scope.bboxActive){

						var minX = Math.min(startX, currentX);
						var minY = Math.min(startY, currentY);
						var maxX = Math.max(startX, currentX);
						var maxY = Math.max(startY, currentY);

						coords = canvasToPDFCoords(minX, minY, maxX	, maxY);

						// find page number
						// TODO this is also done in canvasToPDFCoords, so abstract it into a function
						var pageCanvases = scope.pdf_data.canvasLayer.children();
						var i = 0;
						var pageMaxY = maxY
						var pageCanvas;
						for(i=0; i<pageCanvases.length; i++){
							pageCanvas = pageCanvases[i];
							if (pageMaxY < pageCanvas.height){
								break;
							}
							pageMaxY -= pageCanvas.height;
						}

						if(!inPageRange(scope.selected, i+1)){
							scope.selected.page_num = i+1;
							scope.selected.max_page = null;
						}

						if (scope.selected.offset_obj != null && scope.selected.offset_obj.page_num == i+1){
							coords = subtractByPoint(coords, scope.selected.offset_obj.x0, scope.selected.offset_obj.y0);
						}

						if (scope.selected.bounding_box == null){
							scope.selected.bounding_box = {};
						}
						scope.selected.bounding_box.x0 = coords.x0;
						scope.selected.bounding_box.y0 = coords.y0;
						scope.selected.bounding_box.x1 = coords.x1;
						scope.selected.bounding_box.y1 = coords.y1;

			        } else if (scope.marginActive){
			        	var pdf_y = canvasToPDFCoords(0, currentY, 0, currentY).y0;
			        	scope.selected.nextpage_top = pdf_y;
			        }
					paintCanvas();
		    	}

	    	});

			/**
			* When the user lets go the mouse, deactivate drawing to prevent accidental editing.
			*/
			element.bind('mouseup', function(event){
				// stop drawing, deactive bounding box
				drawing = false;
				scope.bboxActive = false;
				scope.marginActive = false;
				scope.$apply();
			});

			/**
			* Draws bounding boxes on the canvas. Bounding boxes are colored differently 
			* if they are currently selected, enabled or disabled, etc. 
			*/
			function paintCanvas(){
				// clear previous rectangles
				var ctx = element[0].getContext('2d');
				ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
				var color;
				var opacity = 1;
				var coords;

				// draw page borders
				if(scope.pdf_data == undefined){
					return;
				}
				var pageCanvases = scope.pdf_data.canvasLayer.children();
				drawPageBorders(pageCanvases);

				// draw layout elements
				if (scope.pdf_data.layout_elements != undefined){
					scope.pdf_data.layout_elements.forEach(function(layout_element){
						color = "#999999";
						opacity=0.3;

						if (scope.selected && scope.selected.bounding_box){
							// if layout element is on same page as selected field
							if (inPageRange(scope.selected, layout_element.page_num)){
								var selected_bbox = scope.selected.bounding_box;
								// if the selected field's offset object exists for this field on the correct page, 
								// translate the selected field by the appropriate amount before checking which layout elements it intersects with
								if (scope.selected.offset_obj != null && scope.selected.offset_obj.page_num == layout_element.page_num){
									selected_bbox = translateByPoint(scope.selected.bounding_box, scope.selected.offset_obj.x0, scope.selected.offset_obj.y0);
								}

								// check if layout element overlaps with selected field
								if (inBounds(selected_bbox, getCorner(scope.selected.corner, layout_element.bounding_box))){
									color = "#FFAA00";
									opacity=0.5;
								}
							}
						}

						coords = PDFToCanvasCoords(layout_element.bounding_box, layout_element.page_num);
						drawBBOX(coords, color, opacity);
					});
				}

				// draw stuff for each field
				if (scope.extractor().fields != undefined){
					scope.extractor().fields.forEach(function(field){

						// Draw offset boxes
						if (field.offset_obj != null) {
							if (scope.selected && field.applier_key == scope.selected.applier_key){
								color="#009900";
							}
							else {
								color="#999999";
							}
							coords = PDFToCanvasCoords(field.offset_obj, field.offset_obj.page_num); 
							drawBBOX(coords, color, opacity);
						}

						// Draw actual bounding box
						if (scope.selected && field.applier_key == scope.selected.applier_key){
							color = "#FF0000";
						}
						else if (field.enabled == false){
							color = "#AAAAFF";
						}
						else {
							color = "#000099";
						}

						for(var i=0; i<pageCanvases.length; i++){
							opacity = 1;
							if (!inPageRange(field, i+1)){
								opacity=0;	
							}

							if (field.bounding_box != null && field.bounding_box.x0 != null){
								var bbox = field.bounding_box;
								// translate bounding box by the offset object, if it exists on this page
								if (field.offset_obj != null && field.offset_obj.page_num == i+1){
									bbox = translateByPoint(field.bounding_box, field.offset_obj.x0, field.offset_obj.y0);
								}
								coords = PDFToCanvasCoords(bbox, i+1);
								drawBBOX(coords, color, opacity);
							}

							// draw margin for multi-page tables
							if (field.nextpage_top != null && i+1 > field.page_num){
								var y = PDFToCanvasCoords({x0: 0, y0: field.nextpage_top, x1: 0, y1: field.nextpage_top}, i+1).y0;
								drawHorizontalLine(y, pageCanvases[i].width, color, 2, opacity);
							}
						}
					});
				}
			}
			// in case the controller needs to directly get the canvas to redraw; sometimes angular can't handle all events that would require a re-draw
			scope.paintCanvas = paintCanvas;

			function drawPageBorders(pages){
				var current_y = 0;
				for (var i=0; i<pages.length-1; i++){
					current_y += pages[i].height;
					drawHorizontalLine(current_y, pages[i].width, "#000000", 2, 1);
				}
			}

			// draws a horizontal line across a page
			function drawHorizontalLine(y, page_width, color, thickness, opacity){
				var ctx = element[0].getContext('2d');
				ctx.strokeStyle = color;
				ctx.lineWidth = thickness;
				ctx.beginPath();
				ctx.moveTo(0, y);
				ctx.lineTo(page_width, y);
				ctx.stroke();
				ctx.closePath();
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

			//TODO move this somewhere better, maybe in the model file?
			function inPageRange(field, page_num){
				if (page_num != field.page_num){
					if (field.maxpage == null || page_num > field.maxpage || page_num < field.page_num){
						return false;
					}
				}
				return true;
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

			// canvas reset
			function reset(){
				element[0].width = element[0].width; 
			}

			// watch selected field, so one can highlight only the selected bounding box 
			scope.$watchCollection('selected', function(newValue, oldValue){
				paintCanvas();
			});

			// watch extractor, so loading a new extractor re-draws fields
			scope.$watch('extractor()', function(newValue, oldValue){
				paintCanvas();
			});
	    }
	};
});