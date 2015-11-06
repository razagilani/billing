/**
 * @license Copyright (c) 2003-2014, CKSource - Frederico Knabben. All rights reserved.
 * For licensing, see LICENSE.html or http://ckeditor.com/license
 */

CKEDITOR.plugins.addExternal('justify', 'plugins/justify/', 'plugin.js');

CKEDITOR.editorConfig = function( config ) {
    config.height = 500;
    config.autoGrow_minHeight = 500;
    config.autoGrow_onStartup = true;

    config.extraPlugins = 'justify';
	// The toolbar groups arrangement, optimized for two toolbar rows.
	config.toolbarGroups = [
		{ name: 'clipboard',   groups: [ 'clipboard', 'undo' ] },
		{ name: 'editing',     groups: [ 'find', 'selection', 'spellchecker' ] },
		{ name: 'links' },
		{ name: 'insert' },
		{ name: 'forms' },
		{ name: 'tools' },
		{ name: 'document',	   groups: [ 'mode', 'document', 'doctools' ] },
		{ name: 'others' },
		'/',
		{ name: 'basicstyles', groups: [ 'basicstyles', 'cleanup' ] },
		{ name: 'paragraph',   groups: [ 'list', 'indent', 'blocks', 'align', 'bidi' ] },
        { name: 'justify'},
		{ name: 'styles' },
		{ name: 'colors' },
	];

    config.basicEntities = true;
    config.entities = false;
    config.entities_greek = true;
    config.entities_latin = true;
    config.htmlEncodeOutput = false;
    config.entities_processNumerical = false;
    config.allowedContent = true;
    config.ignoreEmptyParagraph = false;

	// Remove some buttons, provided by the standard plugins, which we don't
	// need to have in the Standard(s) toolbar.
	config.removeButtons = 'Underline,Subscript,Superscript';

	// Se the most common block elements.
	config.format_tags = 'p;h1;h2;h3;h4;h5;pre';

	// Make dialogs simpler.
	config.removeDialogTabs = 'image:advanced;link:advanced';
};
