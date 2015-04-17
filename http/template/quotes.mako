<%inherit file="base.mako"/>
<%namespace file="form.mako" import="render_form, render_ext_form"/>
<%def name="sectiontitle()">Quotes</%def>


<div style="width:${self.attr.page_width}; margin-left:auto; margin-right:auto; margin-top:20px; padding-left:${self.attr.page_padding}; padding-right:${self.attr.page_padding};">
    <%
    lis = len(interests)
    %>
    ${render_form([], form.csrf_token, button=None)}
    <div onclick="location.href='${url_for('quote_view', quote_id=quote.id)}'" style="display:table;">
        <div style="display:table-row;">
            <div style="display:table-cell;">Quote ID</div>
            <div style="display:table-cell;">Company</div>
            <div style="display:table-cell;">Rate Class</div>
            <div style="display:table-cell;">Charge</div>
            <div style="display:table-cell;">Rate</div>
            <div style="display:table-cell;">Time Inserted</div>
            <div style="display:table-cell;">Time Issued</div>
            <div style="display:table-cell;">Time Expired</div>
            <div style="display:table-cell;">Units</div>
        </div>

    %for quote in quotes:
    %endfor
    </div>
</div>