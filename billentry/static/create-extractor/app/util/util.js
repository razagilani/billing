"use strict";

/* MATH / GEOMETRY FUNCTIONS */

// scales the coordinates in 'coords' by a factor of 'sc'
function scale(coords, sc){
	return { x0: coords.x0*sc, y0: coords.y0*sc, x1: coords.x1*sc, y1: coords.y1*sc };
}

// Translates org by a given 2d point, by adding its coordinates
function translateByPoint(org, dx, dy){
	return {x0: org.x0+dx, y0: org.y0+dy, x1: org.x1+dx, y1: org.y1+dy };
} 

// Subtracts org by a given 2d point
function subtractByPoint(org, dx, dy){
	return {x0: org.x0-dx, y0: org.y0-dy, x1: org.x1-dx, y1: org.y1-dy };
} 

// Returns the corner of a bounding box, with the following rule:
// 0:	Top Left 
// 1:	Top Right 
// 2:	Bottom Left 
// 3:	Bottom Right
function getCorner(corner, bounds){
    var x = (corner & 1) ? bounds.x1 : bounds.x0;
    var y = (corner & 2) ? bounds.y0 : bounds.y1;
    return {x: x, y: y};
}

// Checks if a certain object's corner is in the bounds a given bounding box
function inBounds(bounds, point){
	return point.x >= bounds.x0 && point.x <= bounds.x1 && point.y >= bounds.y0 && point.y <= bounds.y1;
}

