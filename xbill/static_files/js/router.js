define(function (require) {

    "use strict";

    var $           = require('jquery');
    var Backbone    = require('backbone');

    return Backbone.Router.extend({

        routes: {
            "": "affiliates",
            "content_admin": "content_admin"
        },

        affiliates: function () {
            require(["views/affiliates/app_view"], function (AppView) {
                var view = new AppView();
                view.render();
            });
        },

        content_admin: function(){
            require(["views/content_admin/app_view"],
                function (AppView) {
                    var view = new AppView();
                    view.render();
            });
        }

    });

});