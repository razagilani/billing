require.config({

    // Avoid Caching
    urlArgs: "bc=" + (new Date()).getTime(),

    baseUrl: '../../../../../../../static/js/',

    paths: {
        views: 'views',
        tpl: 'tpl',
        models: 'models',
        rest: '../../rest_api',
        styles : '../css/new',

         // define library paths
        'jquery': 'lib/jquery.min',
        'underscore': 'lib/underscore-min',
        'backbone': 'lib/backbone-min',
        'text': 'lib/text',
        'css': 'lib/css',
        'bootstrap': 'lib/bootstrap.min',
        'csrf': 'lib/csrf',
        'ckeditor': 'lib/ckeditor/ckeditor'
    },

/*
    map: {
        '*': {
            'app/models/employee': 'app/models/memory/employee'
        }
    },
*/

    shim: {
        'backbone': {
            deps: ['underscore', 'jquery'],
            exports: 'Backbone'
        },
        'underscore': {
            exports: '_'
        },
        'csrf': {
            deps: ['jquery']
        }
    }
});

require(['jquery', 'backbone', 'csrf', 'router'],
    function ($, Backbone, csrf, Router) {
    var router = new Router();
    Backbone.history.start();
});