<!DOCTYPE html>
<%!
    company_name = 'Skyline'
    page_width = '1000px'
    page_padding = '20px'
%>

<%def name="extjs()">
  <%
    return False
  %>
</%def>


<%def name="nav()">
    <div id="nav">
        <ul>
            <li><a href="/features.html">billing</a>
                <ul>
                    <li><a href="/features.html">ReeBills</a></li>
                    <li><a href="/organizations.html">Utility Bills</a></li>
                </ul>
            </li>
            <li><a href="/support.html">power & gas</a>
                <ul>
                    <li>
                        <a href="${url_for('customer_interest')}">Customer Interest</a>
                    </li>
                    <li>
                        <a href="${url_for('quotes')}">Quotes</a>
                    </li>
                </ul>
            </li>
            <li><a href="/blog/">metering</a></li>
        </ul>
    </div>
</%def>

<%def name="jsbody()"></%def>

<html lang="en">
    <head>
        <title>${' - '.join([self.sectiontitle(), company_name])}</title>

        <link href='http://fonts.googleapis.com/css?family=Nunito:400,300' rel='stylesheet' type='text/css'>
        <link href='http://fonts.googleapis.com/css?family=Roboto:400,300' rel='stylesheet' type='text/css'>

        %if self.extjs():
            <link href="http://cdn.sencha.com/ext/gpl/4.2.0/resources/css/ext-all.css" rel="stylesheet" />
        %endif
        <link rel="stylesheet" type="text/css" href="/static/style.css" />
        <script src="//ajax.googleapis.com/ajax/libs/jquery/1.11.1/jquery.min.js"></script>
        ${self.jsbody()}
        %if extjs:
            <script src="http://cdn.sencha.com/ext/gpl/4.2.0/ext-all.js"></script>

            <script type="text/javascript">
                $(document).ready(function() {
                    pdta = {
                        title: '${self.sectiontitle()}',
                        collapsible:false,
                        width:'100%',
                        html: $('#panel_content').html()
                    }

                   var element = Ext.getBody().createChild();
                   Ext.widget('panel', Ext.applyIf(pdta, {
                        renderTo: Ext.get('panel_container'),
                        bodyPadding: 0,
                        border: 0
                   }));
                });
            </script>
        %endif
    </head>
    <body>
        <div style="background-color:#f0f0f0; width:100%;">
            <div style="margin-left:auto; margin-right:auto; width:${page_width}; position:relative; padding-left:${page_padding}; padding-right:${page_padding};">
                  <div class="noselect" style="display:table; width:100%; vertical-align:bottom; padding-top:20px; padding-bottom:20px; ">
                      <div style="display:table-cell; color:#000000; width:140px; vertical-align:middle; font-size:36px; font-family: 'Nunito', sans-serif;">
                        ${company_name}
                      </div>
                      <div style="display:table-cell; vertical-align:middle;">
                        <div style="font-family: 'Roboto', sans-serif; font-size:24px; color:#444444; border-left:1px solid #b7b7b7; padding:12px; 0px 12px 12px;">${self.sectiontitle()}</div>
                      </div>
                  </div>
                  ${self.nav()}
            </div>
        </div>
        %if self.extjs():
            <div id="panel_content" style="display:none;"><div style="font-size:14px;" id="panel_body">${next.body()}</div></div>
            <div id="panel_container"></div>
        %else:
            ${next.body()}
        %endif
    </body>
</html>