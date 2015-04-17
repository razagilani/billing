<%namespace file="base.mako" import="extjs"/>

<%def name="render_form(fields, csrf_field=None, method='post', button='Submit', label_width='150px')">
    %if extjs():
        ${render_ext_form(self.sectiontitle, fields)}
    %else:
        <form method="${method}">
            %for field in fields:
                <div class="error" style="padding-left:${label_width}; padding-top:10px;">${field.errors[0] if field.errors else ''}</div>
                <div><div style="width:${label_width}; display:inline-block;">${field.label}</div>${field(style="width:280px;")}</div>
            %endfor
            ${csrf_field()}
            %if button:
                <input type="submit" value="${button}" style="display:block; font-weight:bold; margin-left:130px; margin-top:20px;"/>
            %endif
        </form>
    %endif
</%def>

<%def name="render_ext_form(title, fields)">
    <script type="text/javascript">
        Ext.Loader.setConfig({
            enabled: true
        });
        Ext.Loader.setPath('Ext.ux', '/static/extux');

        Ext.require([
            '*',
            'Ext.ux.DataTip'
         ]);

        Ext.onReady(function() {
            Ext.QuickTips.init();
            var bd = Ext.getBody();
            var required = '<span style="color:red;font-weight:bold" data-qtip="Required">*</span>';
            var simple = Ext.widget({
                xtype: 'form',
                layout: 'form',
                collapsible: true,
                id: 'simpleForm',
                //url: 'save-form.php',
                frame: true,
                title: '${title()}',
                bodyPadding: '5 5 0',
                margin: '0 100 0 100',
                width: 650,
                renderTo: Ext.get(document.body),
                fieldDefaults: {
                    msgTarget: 'side',
                    labelWidth: 150
                },
                plugins: {
                    ptype: 'datatip'
                },
                defaultType: 'textfield',
                items: [

                %for field in fields:
                    <%
                    field_xtype = {'TextAreaField': 'textareafield',
                                   'SelectField': 'selectfield'}.get(field.type, None)
                    %>
                    %if field.type == 'SelectField':
                        {
                            value: '${field.data}',
                            xtype: 'combo',
                            name: 'accountsFilter',
                            fieldLabel: '${field.label}',
                            editable: false,
                            store: new Ext.data.Store({
                                fields: ['label', 'value'],
                                data: [
                                    %for value, label, _ in field.iter_choices():
                                        {label: '${label}', value: '${value}'},
                                    %endfor
                                ]
                            }),
                            triggerAction: 'all',
                            valueField: 'value',
                            displayField: 'label',
                            forceSelection: true,
                            selectOnFocus: true
                        }
                    %else:
                    {
                        %if field_xtype:
                            xtype: '${field_xtype}',
                        %endif
                        fieldLabel: '${field.label}',
                        name: '${field.name}',
                        //success: false,
                        error: 'uh oh',
                        value: '${str(field.data).replace("\n", "\\n")}',


                        }

                       %endif
                    ,
                %endfor

                ],

                errors : {
                    city: 'This is city error'
                },

                buttons: [{
                    text: 'Save',
                    handler: function() {
                        this.up('form').getForm().isValid();
                    }
                }

                ]
            });
        })
    </script>

</%def>