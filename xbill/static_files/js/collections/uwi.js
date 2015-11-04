define(function (require) {

    "use strict";

    var $ = require('jquery');
    var Backbone = require('backbone');
    var UWI = require('models/uwi');

    return Backbone.Collection.extend({
        model: UWI,
        url: '/rest_api/utilitywebsiteinformation'
    });

});