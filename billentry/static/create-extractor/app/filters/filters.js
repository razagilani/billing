'use strict';

angular.module('createExtractor').

// capitalizes first letter of string
filter('capitalize', function() {
    return function(input) {
      if (input == undefined){
        return input;
      }
      return input.replace(/\w\S*/g, function(txt){
        return txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase();
      });
    };
}).

//display the values of a bounding box
filter('bboxToString', function(){
  return function(bbox){
    if (bbox != null && bbox.x0 != null){
      return "x0: " + bbox.x0.toFixed(2) + 
             ", y0: " + bbox.y0.toFixed(2) + 
             ", x1: " + bbox.x1.toFixed(2) + 
             ", y1: " + bbox.y1.toFixed(2);
    }
    else {
      return "(click to draw on PDF)";
    }
  };
}).

filter('singleCoordToString', function(){
  return function(coord, axis){
    if (coord == null){
      return "(click to draw on PDF)";
    }
    else {
      return axis+": "+coord.toFixed(2);
    }
  };
}).

filter('fromListByField', function(){
  return function(list, key, value){
    if (value == undefined){
      return value;
    }
    var result = $.grep(list, function(e){ return e[key] == value; });
    return result[value];
  };
});