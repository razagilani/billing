define(function (require) {

    "use strict";

    var $ = require('jquery');
    var Backbone = require('backbone');

    return Backbone.Model.extend({
        defaults: {
            name: '',
            id: ''
        }
    });

});
