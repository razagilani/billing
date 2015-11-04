define(function (require) {

    "use strict";

    var $ = require('jquery');
    var token = require('text!rest/token');

    $(function(){
          $.ajaxSetup({
            headers: {'X-CSRFToken': token}
          });
    });

    return true;

});