'use strict';

angular.module('createExtractor').

// add service for getting data from server/DB
factory('DBService', ['$http',
  function($http){
    var DBService = {};

    // Each of these functions return a promise that executes the request.

    // Given an id, returns the bill's id , utility_id, and pdf url on success
    DBService.getUtilBill = function(id){
      return $http.get('/get-utilbill/'+id);
    };

    //Returns a list of the applier keys currently available to use in extraction. 
    DBService.getApplierKeys = function(){
      return $http.get('/get-applier-keys');
    };

    // Returns a list of possible field types as a string array
    DBService.getFieldTypes = function(){
      return $http.get('/get-field-types');
    };

    // Returns a list of possible data types for a field as a string array
    DBService.getDataTypes = function(){
      return $http.get('/get-data-types');
    };

    // For a given bill, returns the first object that matches 'regex'. 
    // min_page and max_page can be used to narrow down which pages are searched.
    DBService.getTextLine = function(bill_id, regex, min_page, max_page){
      var min_page_str = (min_page == null) ? "" : "/"+min_page;
      var max_page_str = (max_page == null) ? "" : "/"+max_page;
      return $http.post('/get-text-lines-page/'+bill_id+min_page_str+max_page_str, {regex: regex});
    };

    // Tests a field on a given bill, and returns the output (after the type conversion function has been applier)
    DBService.previewField = function(bill_id, field){
      return $http.post('/preview-field/'+bill_id, field);
    };

    return DBService;
}]);