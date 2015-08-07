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

// Returns a string representing a coordinate on an axis. If the coordinate is null, returns '(click to draw on PDF)'
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

// Given a numerator and a denominator, returns a formatted percentage. 
filter('percentage', function(){
  return function(numerator, denominator){
    if (denominator == 0){
      return "-";
    }
    return (100*numerator/denominator).toFixed(0)+"%";
  };
}).

// Returns the number of keys/members this object has. 
filter('numKeys', function(){
  return function(o){
    return Object.keys(o).length;
  };
}).

// Returns the number of keys/members this object has. 
filter('printField', function(){
  return function(value, type){
    if (type == "address"){
      var out_str = "";
      out_str += (value.addressee || "(no addressee)") + ", ";
      out_str += (value.street || "(no street)") + ", ";
      out_str += (value.city || "(no city)") + ", ";
      out_str += (value.state || "(no state)") + ", ";
      out_str += (value.postal_code || "(no postal code)");
      return out_str;
    } else if (type.match("charges")){
      var out_str = "\n";
      value.forEach(function(charge){
        out_str += "\"" + charge.description + "\": ";
        out_str += charge.quantity + " * " + charge.rate + " = " + charge.target_total;
        out_str += "\n"
      });
      return out_str
    }
    return value;
  };
});