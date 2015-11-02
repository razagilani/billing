define(function (require) {

    "use strict";

    var $ = require('jquery');
    var Backbone = require('backbone');
    var Content = require('models/content');

    var ContentCollection = Backbone.Collection.extend({
        model: Content,
        url: '/rest_api/content',

        comparator: function(content){
            return content.get('name');
        },

        byMaxVersion: function(){
            var tmp = {};
            this.each(function(content){
                if(tmp.hasOwnProperty(content.get('name'))){
                    if(tmp[content.get('name')] < content.get('version')){
                        tmp[content.get('name')] = content.get('version');
                    }
                }else{
                    tmp[content.get('name')] = content.get('version');
                }
            });
            var filtered = this.filter(function(content){
                if(content.get('version') === tmp[content.get('name')]){
                    return true;
                }
            });
            var cc = new ContentCollection(filtered);
            cc.sort();
            return cc;
        },

        byContentName: function(name){
            var filtered = this.filter(function(content){
                if(content.get('name') === name){
                    return true;
                }
            });
            var cc = new ContentCollection(filtered);
            cc.comparator = function(content){
                return -content.get('version');
            }
            cc.sort();
            return cc;
        },

        getMaxVersionModel: function(){
            var maxversion  = null;
            this.each(function(content){
                if(maxversion === null){
                    maxversion = content;
                    return;
                }
                if(content.get('version') > maxversion.get('version')){
                    maxversion = content;
                }
            });

            return maxversion;
        }
    });

    return ContentCollection;

});