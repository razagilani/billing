<!DOCTYPE html>
<%!
    company_name = 'Skyline'
    page_width = '1000px'
    page_padding = '20px'
%>


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
                        <%doc>
                        <ul>
                            <li><a href="http://docs.sqlalchemy.org">New Interest</a></li>
                            <li><a href="http://docs.sqlalchemy.org">Input/Select Offer</a></li>
                            <li><a href="http://docs.sqlalchemy.org">Offer Select</a></li>
                            <li><a href="http://docs.sqlalchemy.org">Customer Accept</a></li>
                            <li><a href="http://docs.sqlalchemy.org">Contract </a></li>
                            <li><a href="http://docs.sqlalchemy.org">Completed</a></li>
                        </ul>
                        </%doc>
                    </li>
                    <li>
                        <a href="${url_for('quotes')}">Quote Data</a>
                    </li>
                </ul>
            </li>
            <li><a href="/blog/">metering</a></li>
        </ul>
    </div>
</%def>

<html lang="en">
    <head>
        <title>${' - '.join([self.sectiontitle(), company_name])}</title>
        <link rel="stylesheet" type="text/css" href="/static/style.css" />
        <link href='http://fonts.googleapis.com/css?family=Nunito:400,300' rel='stylesheet' type='text/css'>
        <link href='http://fonts.googleapis.com/css?family=Roboto:400,300' rel='stylesheet' type='text/css'>
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
        ${next.body()}
    </body>
</html>