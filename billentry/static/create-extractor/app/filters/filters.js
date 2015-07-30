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
      // return input.charAt(0).toUpperCase() + input.substr(1).toLowerCase();
    };
}).

//produces a range of integers
filter('range', function() {
  return function(input, min, max) {
    min = parseInt(min); //Make string input int
    max = parseInt(max);
    for (var i=min; i<=max; i++)
      input.push(i);
    return input;
  };
}).

// if a value is null, display "(none)"
filter('denullify', function(){
  return function(input){
    if (input == null){
      return "(none)";
    }
    else{
      return input;
    }
  };
}).

//display the values of a bounding box
filter('bboxToString', function(){
  return function(bbox){
    if (bbox != null && bbox.x0 != null){
      return "x0: " + bbox.x0 + ", y0: " + bbox.y0 + ", x1: " + bbox.x1 + ", y1: " + bbox.y1;
    }
    else {
      return "(click to draw on PDF)";
    }
  };
});