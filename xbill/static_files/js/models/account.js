define(function (require) {

    "use strict";

    var $ = require('jquery');
    var Backbone = require('backbone');

    return Backbone.Model.extend({
        defaults: {
            first_name: '',
            last_name: '',
            tou_signed: false
        }
    });

});